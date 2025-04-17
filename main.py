import cv2
import clip
import typer
import torch
import chromadb
import whisperx
from PIL import Image
from rich import print
from moviepy.editor import VideoFileClip
from sentence_transformers import SentenceTransformer

app = typer.Typer()

device = "cpu"
embedder  = SentenceTransformer(r"./models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf")
clip_model, preprocess = clip.load("ViT-B/32", device=device)
chroma_client = chromadb.PersistentClient(path="./chroma_data")
voice_collection = chroma_client.get_or_create_collection(name="voiceEmbeddings")
scene_collection = chroma_client.get_or_create_collection(name="sceneEmbeddings")

@app.command()
def videoindex(path: str):

    video = VideoFileClip(path)
    video_audio = video.audio
    audio = "audio.wav"
    video_audio.write_audiofile(audio)

    print("[bold red]Video Indexing...[/bold red]")

    print("[green]Audio Indexing...[/green]")

    batch_size = 16
    compute_type = "float32"

    whisper_model = whisperx.load_model(r"./models/models--Systran--faster-whisper-large-v2/snapshots/f0fe81560cb8b68660e564f55dd99207059c092e", device, compute_type=compute_type)

    audio = whisperx.load_audio(audio)
    result = whisper_model.transcribe(audio, batch_size=batch_size, language="en")

    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device, model_dir="./torch")
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    segments = result["segments"]

    id = 0 
    for segment in segments:
        dialogue = segment["text"]
        dialogue_embedding = embedder.encode(dialogue, convert_to_tensor=True)
        voice_collection.add(ids=[f"{id}"],embeddings=[dialogue_embedding.tolist()], metadatas=[{"start":segment["start"]}])
        id+=1
    
    print("[green]Audio Indexing Complete !!![/green]")

    print("[green]Scene Indexing...[/green]")
    
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
        scene_collection.add(ids=[f"{id}"], embeddings=[embedding_vector], metadatas=[{"time": time}])

        id += 1
        time += frame_time

    video.release()

    print("[green]Scene Indexing Complete !!![/green]")

    print("[bold red]Video Indexing Complete !!![/bold red]")

@app.command()
def dialogue(dialogue: str):

    print("[green]Searching dialogue...[/green]")

    query = dialogue
    query_embedding = embedder.encode(query, convert_to_tensor=True)

    result = voice_collection.query(query_embeddings=[query_embedding.tolist()], include=["metadatas"], n_results=1)
    time = result["metadatas"][0][0]["start"]

    print("[green]Dialogue found !!![/green]")

    return time

@app.command()
def scene(scene: str):

    print("[green]Searching scene...[/green]")

    query = scene
    query = clip.tokenize([query]).to(device)
 
    with torch.no_grad():
        query_features = clip_model.encode_text(query)
        query_features /= query_features.norm(dim=-1, keepdim=True)
     
    query_embedding = query_features.cpu().numpy().tolist()[0]
 
    result = scene_collection.query(query_embeddings=[query_embedding],include=["metadatas"],n_results=1)
 
    time = result["metadatas"][0][0]["time"]

    print("[green]Scene found...[/green]")

    return time

if __name__ == "__main__":
    app()