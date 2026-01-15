"""MinIO/S3 Object Storage client for media files."""

import base64
import io
import os
from datetime import timedelta
from typing import BinaryIO, Optional
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from minio import Minio
from minio.error import S3Error

from app.config import get_settings
from app.media.models import MediaFile, MediaType, MediaStatus


class MediaStorage:
    """MinIO/S3 storage client for media files with encryption support."""
    
    _client: Optional[Minio] = None
    _encryption_key: Optional[bytes] = None
    
    @classmethod
    def connect(cls) -> None:
        """Connect to MinIO."""
        settings = get_settings()
        
        cls._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        
        # Ensure bucket exists
        bucket = settings.minio_bucket
        if not cls._client.bucket_exists(bucket):
            cls._client.make_bucket(bucket)
            print(f"✅ Created MinIO bucket: {bucket}")
        
        # Setup encryption key
        if settings.media_encryption_key:
            cls._encryption_key = base64.b64decode(settings.media_encryption_key)
        
        print(f"✅ MinIO connected: {settings.minio_endpoint}")
    
    @classmethod
    def get_client(cls) -> Minio:
        """Get MinIO client."""
        if not cls._client:
            cls.connect()
        return cls._client
    
    @classmethod
    def upload_file(
        cls,
        user_id: UUID,
        media_type: MediaType,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        encrypt: bool = True,
    ) -> MediaFile:
        """Upload file to storage.
        
        Args:
            user_id: Owner's UUID
            media_type: Type of media (photo, video, voice)
            file_data: File binary data
            filename: Original filename
            content_type: MIME type
            encrypt: Whether to encrypt (default True)
            
        Returns:
            MediaFile with storage metadata
        """
        settings = get_settings()
        client = cls.get_client()
        
        # Generate storage key
        media_id = uuid4()
        ext = os.path.splitext(filename)[1] or ""
        object_key = f"{media_id}{ext}"
        storage_path = f"{user_id}/{media_type.value}s/{object_key}"
        
        # Read file data
        file_data.seek(0)
        data = file_data.read()
        original_size = len(data)
        
        # Encrypt if requested and key available
        encryption_iv = None
        if encrypt and cls._encryption_key:
            data, encryption_iv = cls._encrypt_data(data)
        
        # Upload to MinIO
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_path,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type if not encrypt else "application/octet-stream",
        )
        
        return MediaFile(
            id=media_id,
            user_id=user_id,
            media_type=media_type,
            bucket=settings.minio_bucket,
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            size_bytes=original_size,
            status=MediaStatus.UPLOADED,
            encrypted=encrypt and cls._encryption_key is not None,
            encryption_iv=base64.b64encode(encryption_iv).decode() if encryption_iv else None,
        )
    
    @classmethod
    def download_file(cls, media: MediaFile) -> bytes:
        """Download and decrypt file from storage.
        
        Args:
            media: MediaFile metadata
            
        Returns:
            Decrypted file bytes
        """
        settings = get_settings()
        client = cls.get_client()
        
        storage_path = f"{media.user_id}/{media.media_type.value}s/{media.object_key}"
        
        response = client.get_object(settings.minio_bucket, storage_path)
        data = response.read()
        response.close()
        
        # Decrypt if encrypted
        if media.encrypted and media.encryption_iv and cls._encryption_key:
            iv = base64.b64decode(media.encryption_iv)
            data = cls._decrypt_data(data, iv)
        
        return data
    
    @classmethod
    def get_presigned_url(
        cls,
        media: MediaFile,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Get presigned URL for direct download.
        
        Note: For encrypted files, client must decrypt after download.
        """
        settings = get_settings()
        client = cls.get_client()
        
        storage_path = f"{media.user_id}/{media.media_type.value}s/{media.object_key}"
        
        return client.presigned_get_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_path,
            expires=expires,
        )
    
    @classmethod
    def get_upload_url(
        cls,
        user_id: UUID,
        media_type: MediaType,
        filename: str,
        expires: timedelta = timedelta(hours=1),
    ) -> tuple[UUID, str]:
        """Get presigned URL for direct upload.
        
        Returns:
            Tuple of (media_id, upload_url)
        """
        settings = get_settings()
        client = cls.get_client()
        
        media_id = uuid4()
        ext = os.path.splitext(filename)[1] or ""
        object_key = f"{media_id}{ext}"
        storage_path = f"{user_id}/{media_type.value}s/{object_key}"
        
        url = client.presigned_put_object(
            bucket_name=settings.minio_bucket,
            object_name=storage_path,
            expires=expires,
        )
        
        return media_id, url
    
    @classmethod
    def delete_file(cls, media: MediaFile) -> bool:
        """Delete file from storage."""
        settings = get_settings()
        client = cls.get_client()
        
        storage_path = f"{media.user_id}/{media.media_type.value}s/{media.object_key}"
        
        try:
            client.remove_object(settings.minio_bucket, storage_path)
            return True
        except S3Error:
            return False
    
    @classmethod
    def list_user_media(
        cls,
        user_id: UUID,
        media_type: Optional[MediaType] = None,
    ) -> list[str]:
        """List all media objects for a user."""
        settings = get_settings()
        client = cls.get_client()
        
        prefix = f"{user_id}/"
        if media_type:
            prefix = f"{user_id}/{media_type.value}s/"
        
        objects = client.list_objects(
            bucket_name=settings.minio_bucket,
            prefix=prefix,
            recursive=True,
        )
        
        return [obj.object_name for obj in objects]
    
    @classmethod
    def _encrypt_data(cls, data: bytes) -> tuple[bytes, bytes]:
        """Encrypt data using AES-256-GCM.
        
        Returns:
            Tuple of (encrypted_data, iv)
        """
        if not cls._encryption_key:
            raise ValueError("Encryption key not configured")
        
        # Generate random IV
        iv = os.urandom(12)  # GCM recommends 12 bytes
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(cls._encryption_key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Encrypt
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Append auth tag
        encrypted = ciphertext + encryptor.tag
        
        return encrypted, iv
    
    @classmethod
    def _decrypt_data(cls, encrypted_data: bytes, iv: bytes) -> bytes:
        """Decrypt data using AES-256-GCM."""
        if not cls._encryption_key:
            raise ValueError("Encryption key not configured")
        
        # Extract auth tag (last 16 bytes)
        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(cls._encryption_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        return decryptor.update(ciphertext) + decryptor.finalize()
