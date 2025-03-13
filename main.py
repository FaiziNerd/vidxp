import whisperx
import torch
import clip
import cv2
from sentence_transformers import SentenceTransformer
from moviepy.editor import VideoFileClip
import chromadb
import typer
import gc
from PIL import Image

app = typer.Typer()

embedder  = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_data")
device = "cpu"
clip_model, preprocess = clip.load("ViT-B/32", device=device)
voice_collection = chroma_client.get_or_create_collection(name="voiceEmbeddings")
scene_collection = chroma_client.get_or_create_collection(name="sceneEmbeddings")

@app.command()
def videoindex(path: str):

    print("Audio Indexing...")

    batch_size = 16
    compute_type = "float32"

    filepath = path

    video = VideoFileClip(filepath)
    movie_audio = video.audio
    audio = "audio.wav"
    movie_audio.write_audiofile(audio)

    whisper_model = whisperx.load_model("large-v2", device, compute_type=compute_type)

    audio = whisperx.load_audio(audio)
    result = whisper_model.transcribe(audio, batch_size=batch_size, language="en")

    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    segments = result["segments"]

    id = 0 
    for segment in segments:
        dialogue = segment["text"]
        dialogue_embedding = embedder.encode(dialogue, convert_to_tensor=True)
        voice_collection.add(ids=[f"{id}"],embeddings=[dialogue_embedding.tolist()], metadatas=[{"start":segment["start"]}])
        id+=1
    
    print("Audio Indexing Complete !!!")

    print("Scene Indexing...")

    id = 0
    time = 0.0

    video = cv2.VideoCapture(path)

    fps = video.get(cv2.CAP_PROP_FPS)
    frame_time = 1 / fps
    
    while True:
        ret, frame = video.read()
        if not ret:
            break
        # Convert OpenCV BGR image to RGB and then to PIL Image
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image = preprocess(image).unsqueeze(0).to(device)

        with torch.no_grad():
            image_features = clip_model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)

        embedding_vector = image_features.cpu().numpy().tolist()[0]
        scene_collection.add(ids=[f"{id}"],embeddings=[embedding_vector],metadatas=[{"time": time}])

        id += 1
        time += frame_time

    video.release()
    print("Scene Indexing Complete !!!")

@app.command()
def dialogue(path: str, dialogue: str):

    filepath = path

    query = dialogue
    query_embedding = embedder.encode(query, convert_to_tensor=True)

    result = voice_collection.query(query_embeddings=[query_embedding.tolist()], include=["metadatas"], n_results=1)
    time = result["metadatas"][0][0]["start"]

    def play_from_timestamp(filepath, time):
        video = VideoFileClip(filepath)
        start_time = time
        subclip = video.subclip(start_time)
        subclip.preview()

    play_from_timestamp(filepath, time)

@app.command()
def scene(path: str, scene: str):

    filepath = path
    
    query = scene
    query = clip.tokenize([query]).to(device)

    with torch.no_grad():
        query_features = clip_model.encode_text(query)
        query_features /= query_features.norm(dim=-1, keepdim=True)
    
    query_embedding = query_features.cpu().numpy().tolist()[0]

    result = scene_collection.query(query_embeddings=[query_embedding],include=["metadatas"],n_results=1)

    time = result["metadatas"][0][0]["time"]

    def play_from_timestamp(filepath, time):
        video = VideoFileClip(filepath)
        start_time = time
        subclip = video.subclip(start_time)
        subclip.preview()

    play_from_timestamp(filepath, time)

if __name__ == "__main__":
    app()