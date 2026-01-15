"""Voice Processor - Speech-to-Text and Text-to-Speech for Agent.

Supports:
- STT: OpenAI Whisper (primary) or Google Chirp
- TTS: Google Text-to-Speech or ElevenLabs
"""

import asyncio
import base64
import io
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger("voice_processor")


@dataclass
class VoiceConfig:
    """Voice processing configuration."""
    # STT
    stt_provider: str = "whisper"  # whisper | google
    whisper_model: str = "whisper-1"
    language: str = "ru"
    
    # TTS
    tts_provider: str = "google"  # google | elevenlabs
    voice_name: str = "ru-RU-Wavenet-D"  # Google voice
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    speaking_rate: float = 1.0
    pitch: float = 0.0


class Transcriber:
    """Speech-to-Text using OpenAI Whisper or Google Chirp."""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.settings = get_settings()
    
    async def transcribe(self, audio_bytes: bytes, format: str = "webm") -> str:
        """Transcribe audio to text.
        
        Args:
            audio_bytes: Raw audio data
            format: Audio format (webm, wav, mp3, etc.)
            
        Returns:
            Transcribed text
        """
        if self.config.stt_provider == "whisper":
            return await self._transcribe_whisper(audio_bytes, format)
        elif self.config.stt_provider == "google":
            return await self._transcribe_google(audio_bytes, format)
        else:
            raise ValueError(f"Unknown STT provider: {self.config.stt_provider}")
    
    async def _transcribe_whisper(self, audio_bytes: bytes, format: str) -> str:
        """Transcribe using OpenAI Whisper API."""
        if not self.settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                files={
                    "file": (f"audio.{format}", io.BytesIO(audio_bytes), f"audio/{format}"),
                },
                data={
                    "model": self.config.whisper_model,
                    "language": self.config.language,
                    "response_format": "text",
                },
                timeout=30.0,
            )
            
            response.raise_for_status()
            return response.text.strip()
    
    async def _transcribe_google(self, audio_bytes: bytes, format: str) -> str:
        """Transcribe using Google Speech-to-Text API."""
        # Google Cloud Speech-to-Text
        # Requires GOOGLE_APPLICATION_CREDENTIALS
        try:
            from google.cloud import speech
            
            client = speech.SpeechClient()
            
            audio = speech.RecognitionAudio(content=audio_bytes)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code=self.config.language,
                model="latest_long",
            )
            
            response = await asyncio.to_thread(
                client.recognize,
                config=config,
                audio=audio,
            )
            
            if response.results:
                return response.results[0].alternatives[0].transcript
            return ""
            
        except ImportError:
            logger.warning("Google Cloud Speech not installed, falling back to Whisper")
            return await self._transcribe_whisper(audio_bytes, format)


class Synthesizer:
    """Text-to-Speech using Google TTS or ElevenLabs."""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.settings = get_settings()
    
    async def speak(self, text: str) -> bytes:
        """Convert text to speech audio.
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio bytes (MP3 format)
        """
        if self.config.tts_provider == "google":
            return await self._synthesize_google(text)
        elif self.config.tts_provider == "elevenlabs":
            return await self._synthesize_elevenlabs(text)
        else:
            raise ValueError(f"Unknown TTS provider: {self.config.tts_provider}")
    
    async def _synthesize_google(self, text: str) -> bytes:
        """Synthesize using Google Text-to-Speech API."""
        try:
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.config.language,
                name=self.config.voice_name,
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=self.config.speaking_rate,
                pitch=self.config.pitch,
            )
            
            response = await asyncio.to_thread(
                client.synthesize_speech,
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            
            return response.audio_content
            
        except ImportError:
            logger.warning("Google Cloud TTS not installed, falling back to ElevenLabs")
            return await self._synthesize_elevenlabs(text)
    
    async def _synthesize_elevenlabs(self, text: str) -> bytes:
        """Synthesize using ElevenLabs API."""
        elevenlabs_key = getattr(self.settings, 'elevenlabs_api_key', None)
        if not elevenlabs_key:
            raise ValueError("ElevenLabs API key not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.elevenlabs_voice_id}",
                headers={
                    "xi-api-key": elevenlabs_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
                timeout=30.0,
            )
            
            response.raise_for_status()
            return response.content


class VoiceProcessor:
    """Main voice processing pipeline."""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.transcriber = Transcriber(self.config)
        self.synthesizer = Synthesizer(self.config)
        self._agent_executor = None
    
    @property
    def agent_executor(self):
        """Lazy load agent executor."""
        if self._agent_executor is None:
            from app.agent.executor import get_executor
            self._agent_executor = get_executor()
        return self._agent_executor
    
    async def process(
        self,
        audio_bytes: bytes,
        user_id: str,
        audio_format: str = "webm",
        return_audio: bool = True,
    ) -> dict:
        """Process voice input and generate voice response.
        
        Args:
            audio_bytes: Input audio data
            user_id: User ID for agent context
            audio_format: Audio format (webm, wav, mp3)
            return_audio: Whether to generate audio response
            
        Returns:
            {
                "user_text": str,        # Transcribed user input
                "agent_text": str,       # Agent response text
                "audio": bytes | None,   # Audio response (if return_audio=True)
                "audio_format": str,     # "mp3"
            }
        """
        logger.info(f"Processing voice input for user {user_id}")
        
        # 1. Speech-to-Text
        user_text = await self.transcriber.transcribe(audio_bytes, audio_format)
        logger.info(f"Transcribed: {user_text[:100]}...")
        
        if not user_text.strip():
            return {
                "user_text": "",
                "agent_text": "Извините, я не расслышал. Попробуйте ещё раз.",
                "audio": None,
                "audio_format": "mp3",
            }
        
        # 2. Agent Reasoning
        from app.agent.factory import get_factory
        from app.agent.models import AgentTask
        from uuid import UUID
        
        try:
            factory = get_factory()
            agent = await factory.get_agent(UUID(user_id))
            
            if not agent:
                # Create agent on the fly
                agent = await factory.create_agent(UUID(user_id))
            
            task = AgentTask(
                agent_id=agent.id,
                instruction=user_text,
                max_iterations=5,  # Faster for voice
            )
            
            task = await self.agent_executor.execute_task(task, agent)
            agent_text = task.result or "Произошла ошибка при обработке запроса."
            
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            agent_text = "Извините, произошла ошибка. Попробуйте позже."
        
        logger.info(f"Agent response: {agent_text[:100]}...")
        
        # 3. Text-to-Speech (optional)
        audio_response = None
        if return_audio:
            try:
                audio_response = await self.synthesizer.speak(agent_text)
            except Exception as e:
                logger.error(f"TTS failed: {e}")
        
        return {
            "user_text": user_text,
            "agent_text": agent_text,
            "audio": audio_response,
            "audio_format": "mp3",
        }
    
    async def transcribe_only(self, audio_bytes: bytes, format: str = "webm") -> str:
        """Just transcribe audio without agent processing."""
        return await self.transcriber.transcribe(audio_bytes, format)
    
    async def speak_only(self, text: str) -> bytes:
        """Just convert text to speech."""
        return await self.synthesizer.speak(text)


# Singleton
_processor: Optional[VoiceProcessor] = None


def get_voice_processor() -> VoiceProcessor:
    """Get voice processor singleton."""
    global _processor
    if _processor is None:
        _processor = VoiceProcessor()
    return _processor
