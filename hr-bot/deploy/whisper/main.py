"""
Whisper API Service - 音频转录服务
"""

import os
import tempfile
import logging
from typing import Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import whisper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Whisper Audio Transcription API",
    description="基于OpenAI Whisper的音频转录服务",
    version="1.0.0"
)

# Load Whisper model (medium size for balance of speed and accuracy)
# Available models: tiny, base, small, medium, large
logger.info("Loading Whisper model...")
model = whisper.load_model("medium")
logger.info("Whisper model loaded successfully")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "whisper-api",
        "model": "medium",
        "version": "1.0.0"
    }


@app.post("/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(..., description="音频文件 (AAC, MP3, WAV, M4A)"),
    language: Optional[str] = "zh",  # 默认中文
    task: Optional[str] = "transcribe"  # transcribe 或 translate
):
    """
    转录音频文件为文本
    
    - audio_file: 音频文件
    - language: 音频语言 (默认中文 'zh')
    - task: 任务类型 ('transcribe' 转录, 'translate' 翻译为英文)
    """
    temp_file_path = None
    
    try:
        # Validate file type
        allowed_extensions = {'.aac', '.mp3', '.wav', '.m4a', '.mp4', '.webm'}
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式: {file_ext}. 支持的格式: {allowed_extensions}"
            )
        
        # Save uploaded file to temp directory
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"Received audio file: {audio_file.filename}, size: {len(content)} bytes")
        
        # Transcribe using Whisper
        logger.info(f"Starting transcription with language={language}, task={task}")
        
        result = model.transcribe(
            temp_file_path,
            language=language,
            task=task,
            fp16=False  # Use FP32 for better compatibility
        )
        
        transcription_text = result["text"].strip()
        
        logger.info(f"Transcription completed. Text length: {len(transcription_text)} characters")
        
        return {
            "success": True,
            "transcript": transcription_text,
            "language": result.get("language", language),
            "duration": result.get("duration"),
            "filename": audio_file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")


@app.post("/transcribe-batch")
async def transcribe_batch(
    audio_files: list[UploadFile] = File(..., description="多个音频文件"),
    language: Optional[str] = "zh"
):
    """
    批量转录音频文件
    """
    results = []
    
    for audio_file in audio_files:
        temp_file_path = None
        
        try:
            # Save uploaded file
            file_ext = os.path.splitext(audio_file.filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                content = await audio_file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # Transcribe
            result = model.transcribe(temp_file_path, language=language, fp16=False)
            
            results.append({
                "filename": audio_file.filename,
                "success": True,
                "transcript": result["text"].strip(),
                "language": result.get("language", language)
            })
            
        except Exception as e:
            logger.error(f"Failed to transcribe {audio_file.filename}: {e}")
            results.append({
                "filename": audio_file.filename,
                "success": False,
                "error": str(e)
            })
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
    
    return {
        "success": True,
        "results": results,
        "total": len(audio_files),
        "successful": sum(1 for r in results if r["success"])
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
