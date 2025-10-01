# ================================
# FILE: app/services/voice_profile_service.py
# ================================

import os
import json
import librosa
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import logging

from app.models.voice_profiles import *
from app.interfaces.audio_processor_interface import IAudioProcessor
from app.core.enhanced_exceptions import *
from app.core.config import settings

logger = logging.getLogger(__name__)

class VoiceProfileService:
    """Service for managing user voice profiles and recording sessions"""
    
    # Predefined prompts for voice recording
    RECORDING_PROMPTS = [
        "Hello, this is my voice. I'm recording this sample for voice cloning.",
        "The quick brown fox jumps over the lazy dog near the riverbank.",
        "I love using technology to create amazing experiences for everyone.",
        "My voice is unique and I want to preserve its natural characteristics.",
        "Weather forecast shows sunny skies with temperatures reaching seventy degrees.",
        "Please remember to speak clearly and maintain consistent volume levels.",
        "Artificial intelligence is transforming how we interact with computers.",
        "This voice cloning technology will help me communicate more effectively.",
        "I'm excited to see how accurately this system can replicate my voice.",
        "Thank you for helping me create a digital version of my voice.",
        "Numbers and dates: January first, two thousand twenty-four, at 3:45 PM.",
        "Reading this text helps the system learn my pronunciation patterns.",
        "My voice has its own rhythm, tone, and unique speaking characteristics.",
        "The system analyzes vocal patterns to create an accurate voice model.",
        "This is the final recording sample for my voice profile creation."
    ]
    
    def __init__(self, audio_processor: IAudioProcessor):
        self.audio_processor = audio_processor
        self.profiles_dir = "voice_profiles"
        self.recordings_dir = "voice_recordings" 
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.recordings_dir, exist_ok=True)
        
        # In-memory cache for active sessions
        self.active_sessions: Dict[str, VoiceProfile] = {}
    
    async def start_recording_session(self, user_id: str, request: VoiceRecordingRequest) -> VoiceRecordingSessionResponse:
        """Start a new voice recording session"""
        try:
            # Create voice profile
            profile = VoiceProfile(
                user_id=user_id,
                profile_name=request.profile_name,
                description=request.description,
                total_steps=request.total_steps,
                status=VoiceProfileStatus.RECORDING
            )
            
            # Create recording steps with prompts
            selected_prompts = self.RECORDING_PROMPTS[:request.total_steps]
            for i, prompt in enumerate(selected_prompts, 1):
                step = RecordingStep(
                    step_number=i,
                    text_prompt=prompt
                )
                profile.recording_steps.append(step)
            
            # Save profile and add to active sessions
            await self._save_profile(profile)
            self.active_sessions[profile.profile_id] = profile
            
            logger.info(f"Started recording session for user {user_id}", 
                       extra={"profile_id": profile.profile_id, "total_steps": request.total_steps})
            
            return VoiceRecordingSessionResponse(
                success=True,
                profile_id=profile.profile_id,
                current_step=1,
                total_steps=profile.total_steps,
                next_prompt=profile.recording_steps[0].text_prompt,
                progress_percentage=0.0,
                message=f"Recording session started! Please record: '{profile.recording_steps[0].text_prompt}'"
            )
            
        except Exception as e:
            logger.error(f"Failed to start recording session: {e}")
            raise SystemException(
                message=f"Failed to start recording session: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                user_message="Unable to start voice recording. Please try again."
            )
    
    async def submit_recording_step(self, user_id: str, request: VoiceRecordingStepRequest, audio_file_path: str) -> VoiceRecordingSessionResponse:
        """Submit a recording for a specific step"""
        try:
            # Get profile
            profile = await self._get_profile(request.profile_id)
            if not profile or profile.user_id != user_id:
                raise ValidationException(
                    message="Profile not found or access denied",
                    error_code=ErrorCode.FILE_NOT_FOUND,
                    user_message="Voice profile not found"
                )
            
            if request.step_number < 1 or request.step_number > len(profile.recording_steps):
                raise ValidationException(
                    message=f"Invalid step number: {request.step_number}",
                    error_code=ErrorCode.INVALID_INPUT,
                    user_message="Invalid recording step"
                )
            
            # Analyze audio quality
            audio_analysis = await self._analyze_recording_quality(audio_file_path, profile.recording_steps[request.step_number - 1].text_prompt)
            
            # Update recording step
            step = profile.recording_steps[request.step_number - 1]
            step.audio_file_id = os.path.basename(audio_file_path)
            step.duration = audio_analysis["duration"]
            step.quality_score = audio_analysis["quality_score"]
            step.completed = True
            
            # Move audio file to profile directory
            profile_audio_dir = os.path.join(self.recordings_dir, profile.profile_id)
            os.makedirs(profile_audio_dir, exist_ok=True)
            
            final_audio_path = os.path.join(profile_audio_dir, f"step_{request.step_number:02d}.wav")
            os.rename(audio_file_path, final_audio_path)
            step.recording_url = final_audio_path
            
            # Update profile progress
            profile.completed_steps = sum(1 for s in profile.recording_steps if s.completed)
            progress_percentage = (profile.completed_steps / profile.total_steps) * 100
            
            # Check if recording is complete
            if profile.completed_steps >= profile.total_steps:
                await self._finalize_voice_profile(profile)
                next_prompt = None
                message = "🎉 Voice recording complete! Processing your voice profile..."
            else:
                next_step_idx = profile.completed_steps
                next_prompt = profile.recording_steps[next_step_idx].text_prompt
                message = f"Step {request.step_number} recorded! Next: '{next_prompt}'"
            
            # Save updated profile
            profile.updated_at = datetime.now()
            await self._save_profile(profile)
            self.active_sessions[profile.profile_id] = profile
            
            logger.info(f"Recording step {request.step_number} completed", 
                       extra={"profile_id": profile.profile_id, "quality_score": audio_analysis["quality_score"]})
            
            return VoiceRecordingSessionResponse(
                success=True,
                profile_id=profile.profile_id,
                current_step=profile.completed_steps + 1,
                total_steps=profile.total_steps,
                next_prompt=next_prompt,
                progress_percentage=progress_percentage,
                message=message
            )
            
        except Exception as e:
            if isinstance(e, EnhancedException):
                raise
            logger.error(f"Failed to submit recording step: {e}")
            raise SystemException(
                message=f"Failed to process recording: {str(e)}",
                error_code=ErrorCode.AUDIO_PROCESSING_ERROR,
                user_message="Failed to process your recording. Please try again."
            )
    
    async def _analyze_recording_quality(self, audio_path: str, expected_text: str) -> Dict[str, Any]:
        """Analyze quality of a recording"""
        try:
            # Load audio
            audio_data, sr = await self.audio_processor.load_audio(audio_path)
            duration = len(audio_data) / sr
            
            quality_score = 100.0
            issues = []
            
            # Duration check
            if duration < 2.0:
                quality_score -= 20
                issues.append("Recording too short")
            elif duration > 15.0:
                quality_score -= 10
                issues.append("Recording too long")
            
            # Volume check
            max_amplitude = np.max(np.abs(audio_data))
            if max_amplitude < 0.1:
                quality_score -= 25
                issues.append("Volume too low")
            elif max_amplitude > 0.95:
                quality_score -= 15
                issues.append("Audio may be clipped")
            
            # Noise analysis
            noise_threshold = 0.02
            silence_mask = np.abs(audio_data) < noise_threshold
            noise_ratio = np.sum(silence_mask) / len(audio_data)
            
            if noise_ratio > 0.3:
                quality_score -= 20
                issues.append("High background noise")
            
            # Consistency check (simple RMS analysis)
            frame_size = 2048
            rms_values = []
            for i in range(0, len(audio_data) - frame_size, frame_size):
                frame = audio_data[i:i + frame_size]
                rms = np.sqrt(np.mean(frame**2))
                rms_values.append(rms)
            
            if len(rms_values) > 0:
                rms_std = np.std(rms_values)
                if rms_std > 0.1:
                    quality_score -= 10
                    issues.append("Inconsistent volume")
            
            quality_score = max(0, quality_score)
            
            return {
                "duration": duration,
                "quality_score": quality_score,
                "max_amplitude": float(max_amplitude),
                "noise_ratio": float(noise_ratio),
                "issues": issues,
                "suitable": quality_score >= 60
            }
            
        except Exception as e:
            logger.error(f"Audio quality analysis failed: {e}")
            return {
                "duration": 0,
                "quality_score": 50,
                "issues": ["Analysis failed"],
                "suitable": False
            }
    
    async def _finalize_voice_profile(self, profile: VoiceProfile):
        """Finalize voice profile after all recordings are complete"""
        try:
            profile.status = VoiceProfileStatus.PROCESSING
            
            # Calculate overall metrics
            completed_steps = [s for s in profile.recording_steps if s.completed]
            
            if completed_steps:
                profile.overall_quality_score = np.mean([s.quality_score for s in completed_steps])
                profile.total_duration = sum(s.duration for s in completed_steps)
                
                # Determine quality level
                if profile.overall_quality_score >= 90:
                    profile.quality = VoiceQuality.EXCELLENT
                elif profile.overall_quality_score >= 75:
                    profile.quality = VoiceQuality.GOOD
                elif profile.overall_quality_score >= 60:
                    profile.quality = VoiceQuality.FAIR
                else:
                    profile.quality = VoiceQuality.POOR
            
            # Create concatenated audio file for voice training
            await self._create_voice_embedding(profile)
            
            profile.status = VoiceProfileStatus.READY
            profile.updated_at = datetime.now()
            
            logger.info(f"Voice profile finalized", 
                       extra={"profile_id": profile.profile_id, "quality": profile.quality})
            
        except Exception as e:
            logger.error(f"Failed to finalize voice profile: {e}")
            profile.status = VoiceProfileStatus.FAILED
    
    async def _create_voice_embedding(self, profile: VoiceProfile):
        """Create voice embedding from all recordings"""
        try:
            # Concatenate all audio files
            combined_audio = []
            for step in profile.recording_steps:
                if step.completed and step.recording_url:
                    audio_data, _ = await self.audio_processor.load_audio(step.recording_url)
                    combined_audio.append(audio_data)
            
            if combined_audio:
                # Concatenate with small gaps
                gap = np.zeros(int(0.2 * profile.sample_rate))  # 0.2 second gap
                full_audio = np.concatenate([np.concatenate([audio, gap]) for audio in combined_audio])
                
                # Save combined audio
                embedding_path = os.path.join(self.recordings_dir, profile.profile_id, "voice_embedding.wav")
                await self.audio_processor.save_audio(full_audio, embedding_path, profile.sample_rate)
                
                profile.voice_embedding = embedding_path
                
        except Exception as e:
            logger.error(f"Failed to create voice embedding: {e}")
            raise
    
    async def get_user_profiles(self, user_id: str) -> VoiceProfileListResponse:
        """Get all voice profiles for a user"""
        try:
            profiles = []
            
            # Load profiles from disk
            if os.path.exists(self.profiles_dir):
                for filename in os.listdir(self.profiles_dir):
                    if filename.endswith('.json'):
                        profile_path = os.path.join(self.profiles_dir, filename)
                        try:
                            with open(profile_path, 'r') as f:
                                profile_data = json.load(f)
                                if profile_data.get('user_id') == user_id:
                                    profile = VoiceProfile(**profile_data)
                                    profiles.append(profile)
                        except Exception as e:
                            logger.warning(f"Failed to load profile {filename}: {e}")
            
            # Sort by creation date (newest first)
            profiles.sort(key=lambda p: p.created_at, reverse=True)
            
            return VoiceProfileListResponse(
                profiles=profiles,
                total_count=len(profiles)
            )
            
        except Exception as e:
            logger.error(f"Failed to get user profiles: {e}")
            raise SystemException(
                message=f"Failed to load voice profiles: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                user_message="Unable to load your voice profiles. Please try again."
            )
    
    async def use_voice_profile(self, user_id: str, request: VoiceUsageRequest) -> Dict[str, Any]:
        """Use a voice profile for text-to-speech synthesis"""
        try:
            # Get and validate profile
            profile = await self._get_profile(request.profile_id)
            if not profile or profile.user_id != user_id:
                raise ValidationException(
                    message="Profile not found or access denied",
                    error_code=ErrorCode.FILE_NOT_FOUND,
                    user_message="Voice profile not found"
                )
            
            if profile.status != VoiceProfileStatus.READY:
                raise ValidationException(
                    message=f"Profile not ready, status: {profile.status}",
                    error_code=ErrorCode.INVALID_INPUT,
                    user_message=f"Voice profile is not ready (status: {profile.status})"
                )
            
            if not profile.voice_embedding or not os.path.exists(profile.voice_embedding):
                raise ValidationException(
                    message="Voice embedding not found",
                    error_code=ErrorCode.FILE_NOT_FOUND,
                    user_message="Voice profile data is missing. Please re-record your voice."
                )
            
            # Update usage statistics
            profile.times_used += 1
            profile.last_used = datetime.now()
            await self._save_profile(profile)
            
            # Return voice profile info for TTS synthesis
            return {
                "profile_id": profile.profile_id,
                "profile_name": profile.profile_name,
                "voice_embedding_path": profile.voice_embedding,
                "quality": profile.quality,
                "sample_rate": profile.sample_rate,
                "text": request.text,
                "language": request.language,
                "speed": request.speed,
                "emotion": request.emotion
            }
            
        except Exception as e:
            if isinstance(e, EnhancedException):
                raise
            logger.error(f"Failed to use voice profile: {e}")
            raise SystemException(
                message=f"Failed to use voice profile: {str(e)}",
                error_code=ErrorCode.UNKNOWN_ERROR,
                user_message="Unable to use voice profile. Please try again."
            )
    
    async def delete_voice_profile(self, user_id: str, profile_id: str) -> bool:
        """Delete a voice profile"""
        try:
            profile = await self._get_profile(profile_id)
            if not profile or profile.user_id != user_id:
                return False
            
            # Delete files
            profile_audio_dir = os.path.join(self.recordings_dir, profile_id)
            if os.path.exists(profile_audio_dir):
                import shutil
                shutil.rmtree(profile_audio_dir)
            
            # Delete profile file
            profile_path = os.path.join(self.profiles_dir, f"{profile_id}.json")
            if os.path.exists(profile_path):
                os.remove(profile_path)
            
            # Remove from active sessions
            if profile_id in self.active_sessions:
                del self.active_sessions[profile_id]
            
            logger.info(f"Voice profile deleted", extra={"profile_id": profile_id, "user_id": user_id})
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete voice profile: {e}")
            return False
    
    async def _get_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """Get profile by ID"""
        # Check active sessions first
        if profile_id in self.active_sessions:
            return self.active_sessions[profile_id]
        
        # Load from disk
        profile_path = os.path.join(self.profiles_dir, f"{profile_id}.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    profile_data = json.load(f)
                    return VoiceProfile(**profile_data)
            except Exception as e:
                logger.error(f"Failed to load profile {profile_id}: {e}")
        
        return None
    
    async def _save_profile(self, profile: VoiceProfile):
        """Save profile to disk"""
        profile_path = os.path.join(self.profiles_dir, f"{profile.profile_id}.json")
        
        # Convert to dict for JSON serialization
        profile_dict = profile.dict()
        
        # Handle datetime serialization
        if profile_dict.get('created_at'):
            profile_dict['created_at'] = profile.created_at.isoformat()
        if profile_dict.get('updated_at'):
            profile_dict['updated_at'] = profile.updated_at.isoformat()
        if profile_dict.get('last_used'):
            profile_dict['last_used'] = profile.last_used.isoformat() if profile.last_used else None
        
        with open(profile_path, 'w') as f:
            json.dump(profile_dict, f, indent=2)
