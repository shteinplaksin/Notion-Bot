"""
Модуль для работы с файлами в NotesBot
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import asyncio

logger = logging.getLogger(__name__)


class FileManager:
    """Менеджер файлов"""
    
    def __init__(self, base_path: str = "files"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Создаем подпапки
        self.images_path = self.base_path / "images"
        self.documents_path = self.base_path / "documents"
        self.audio_path = self.base_path / "audio"
        self.temp_path = self.base_path / "temp"
        
        for path in [self.images_path, self.documents_path, self.audio_path, self.temp_path]:
            path.mkdir(exist_ok=True)
        
        # Настройки
        self.max_file_sizes = {
            'image': 10 * 1024 * 1024,  # 10MB
            'document': 20 * 1024 * 1024,  # 20MB
            'audio': 50 * 1024 * 1024,  # 50MB
        }
        
        self.allowed_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'document': ['.pdf', '.doc', '.docx', '.txt', '.md'],
            'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.opus']
        }
    
    async def save_file(self, file_content: bytes, file_name: str, 
                       file_type: str, user_id: int) -> Dict[str, Any]:
        """Сохранение файла"""
        try:
            # Определяем тип файла
            file_category = self._get_file_category(file_name)
            if file_category == 'unknown':
                return {'success': False, 'error': 'Неподдерживаемый тип файла'}
            
            # Проверяем размер
            if len(file_content) > self.max_file_sizes.get(file_category, 5*1024*1024):
                return {'success': False, 'error': 'Файл слишком большой'}
            
            # Генерируем уникальное имя файла
            file_extension = Path(file_name).suffix.lower()
            unique_name = f"{user_id}_{uuid.uuid4().hex}{file_extension}"
            
            # Определяем путь сохранения
            if file_category == 'image':
                file_path = self.images_path / unique_name
            elif file_category == 'document':
                file_path = self.documents_path / unique_name
            elif file_category == 'audio':
                file_path = self.audio_path / unique_name
            else:
                file_path = self.temp_path / unique_name
            
            # Сохраняем файл асинхронно
            try:
                import aiofiles
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(file_content)
            except ImportError:
                # Fallback к синхронному сохранению
                with open(file_path, 'wb') as f:
                    f.write(file_content)
            
            # Вычисляем хеш файла
            file_hash = hashlib.md5(file_content).hexdigest()
            
            return {
                'success': True,
                'file_id': unique_name,
                'file_path': str(file_path),
                'file_size': len(file_content),
                'file_hash': file_hash,
                'file_category': file_category,
                'original_name': file_name
            }
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Получение файла"""
        try:
            # Ищем файл во всех папках
            for folder in [self.images_path, self.documents_path, self.audio_path, self.temp_path]:
                file_path = folder / file_id
                if file_path.exists():
                    try:
                        import aiofiles
                        async with aiofiles.open(file_path, 'rb') as f:
                            content = await f.read()
                    except ImportError:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                    
                    return {
                        'success': True,
                        'content': content,
                        'path': str(file_path),
                        'size': len(content),
                        'category': self._get_file_category_by_path(folder)
                    }
            
            return {'success': False, 'error': 'Файл не найден'}
            
        except Exception as e:
            logger.error(f"Error getting file: {e}")
            return {'success': False, 'error': str(e)}
    
    async def delete_file(self, file_id: str) -> bool:
        """Удаление файла"""
        try:
            for folder in [self.images_path, self.documents_path, self.audio_path, self.temp_path]:
                file_path = folder / file_id
                if file_path.exists():
                    file_path.unlink()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def _get_file_category(self, file_name: str) -> str:
        """Определение категории файла по имени"""
        extension = Path(file_name).suffix.lower()
        
        for category, extensions in self.allowed_types.items():
            if extension in extensions:
                return category
        
        return 'unknown'
    
    def _get_file_category_by_path(self, folder_path: Path) -> str:
        """Определение категории файла по пути папки"""
        folder_name = folder_path.name
        if folder_name == 'images':
            return 'image'
        elif folder_name == 'documents':
            return 'document'
        elif folder_name == 'audio':
            return 'audio'
        else:
            return 'unknown'


class VoiceToTextConverter:
    """Конвертер голоса в текст"""
    
    def __init__(self):
        self.supported_formats = ['.ogg', '.mp3', '.wav', '.m4a', '.opus']
    
    def _blocking_speech_recognition(self, wav_path: str, language: str) -> str:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=language)
        return text

    async def convert_voice_to_text(self, file_path: str, language: str = 'ru-RU') -> Dict[str, Any]:
        """Конвертация голосового сообщения в текст"""
        try:
            # Пытаемся использовать SpeechRecognition
            try:
                import speech_recognition as sr
                
                recognizer = sr.Recognizer()
                
                # Конвертируем в WAV если нужно
                wav_path = await self._convert_to_wav(file_path)
                
                # Распознаем речь
                text = await asyncio.to_thread(self._blocking_speech_recognition, wav_path, language)
                
                # Удаляем временный файл
                if wav_path != file_path:
                    try:
                        os.unlink(wav_path)
                    except:
                        pass
                
                return {
                    'success': True,
                    'text': text,
                    'confidence': 0.8,
                    'language': language
                }
                
            except ImportError:
                # Fallback если библиотеки нет
                return {
                    'success': True,
                    'text': f"Голосовое сообщение (файл: {Path(file_path).name})",
                    'confidence': 0.5,
                    'language': language
                }
            except sr.UnknownValueError:
                return {'success': False, 'error': 'Не удалось распознать речь'}
            except sr.RequestError as e:
                return {'success': False, 'error': f'Ошибка сервиса распознавания: {e}'}
            
        except Exception as e:
            logger.error(f"Error converting voice to text: {e}")
            return {'success': False, 'error': str(e)}
    
    def _blocking_convert_to_wav(self, file_path: str, file_extension: str) -> str:
        from pydub import AudioSegment
        
        if file_extension == '.ogg':
            audio = AudioSegment.from_ogg(file_path)
        elif file_extension == '.mp3':
            audio = AudioSegment.from_mp3(file_path)
        elif file_extension == '.m4a':
            audio = AudioSegment.from_file(file_path, format="m4a")
        elif file_extension == '.opus':
            audio = AudioSegment.from_file(file_path, format="opus")
        else:
            audio = AudioSegment.from_file(file_path)
        
        wav_path = file_path.replace(file_extension, '.wav')
        audio.export(wav_path, format="wav")
        return wav_path

    async def _convert_to_wav(self, file_path: str) -> str:
        """Конвертация аудио в WAV формат"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.wav':
            return file_path
        
        try:
            wav_path = await asyncio.to_thread(self._blocking_convert_to_wav, file_path, file_extension)
            return wav_path
            
        except ImportError:
            # Если pydub не установлен, возвращаем оригинальный файл
            return file_path
        except Exception as e:
            logger.error(f"Error converting audio to WAV: {e}")
            return file_path


class DocumentProcessor:
    """Процессор документов"""
    
    def __init__(self):
        pass
    
    async def extract_text_from_document(self, file_path: str) -> Dict[str, Any]:
        """Извлечение текста из документа"""
        try:
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension == '.txt':
                return await self._extract_from_txt(file_path)
            elif file_extension == '.pdf':
                return await self._extract_from_pdf(file_path)
            elif file_extension in ['.doc', '.docx']:
                return await self._extract_from_word(file_path)
            elif file_extension == '.md':
                return await self._extract_from_txt(file_path)
            else:
                return {
                    'success': True,
                    'text': f"Документ загружен: {Path(file_path).name}"
                }
        
        except Exception as e:
            logger.error(f"Error extracting text from document: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _extract_from_txt(self, file_path: str) -> Dict[str, Any]:
        """Извлечение текста из TXT файла"""
        try:
            try:
                import aiofiles
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    text = await f.read()
            except ImportError:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            return {'success': True, 'text': text}
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            for encoding in ['cp1251', 'latin1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        text = f.read()
                    return {'success': True, 'text': text}
                except:
                    continue
            return {'success': False, 'error': 'Не удалось определить кодировку файла'}
    
    def _blocking_pdf_extraction(self, file_path: str) -> str:
        import PyPDF2
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text

    async def _extract_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """Извлечение текста из PDF файла"""
        try:
            text = await asyncio.to_thread(self._blocking_pdf_extraction, file_path)
            return {'success': True, 'text': text}
        except ImportError:
            return {'success': True, 'text': f'PDF документ: {Path(file_path).name}'}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка чтения PDF: {e}'}
    
    def _blocking_word_extraction(self, file_path: str) -> str:
        import docx
        doc = docx.Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text

    async def _extract_from_word(self, file_path: str) -> Dict[str, Any]:
        """Извлечение текста из Word документа"""
        try:
            text = await asyncio.to_thread(self._blocking_word_extraction, file_path)
            return {'success': True, 'text': text}
        except ImportError:
            return {'success': True, 'text': f'Word документ: {Path(file_path).name}'}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка чтения Word документа: {e}'}


# Глобальные экземпляры
file_manager = FileManager()
voice_converter = VoiceToTextConverter()
document_processor = DocumentProcessor()