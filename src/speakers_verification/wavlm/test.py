import os
import torch
import librosa
import numpy as np
from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
from sklearn.cluster import AgglomerativeClustering

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

def load_audio(file_path, sample_rate=16000):
    audio, sr = librosa.load(file_path, sr=sample_rate)
    return audio

def divide_audio_into_segments(audio, segment_duration=5, sr=16000):
    segment_length = segment_duration * sr
    segments = [audio[i:i+segment_length] for i in range(0, len(audio), segment_length)]
    return [segment for segment in segments if len(segment) == segment_length]  # 마지막 세그먼트가 짧으면 제외

def get_embedding(audio_segment, feature_extractor, model):
    inputs = feature_extractor(audio_segment, sampling_rate=16000, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        embeddings = model(**inputs).embeddings
    return torch.nn.functional.normalize(embeddings, dim=-1).cpu()

def distinguish_speakers_in_file(audio_file, threshold=0.05, segment_duration=5):
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
    model = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv').to(device)

    audio = load_audio(audio_file)
    segments = divide_audio_into_segments(audio, segment_duration)

    embeddings = []
    for segment in segments:
        embedding = get_embedding(segment, feature_extractor, model)
        embeddings.append(embedding.squeeze())

    embeddings = torch.stack(embeddings)
    
    distances = 1 - torch.mm(embeddings, embeddings.t())
    distances_cpu = distances.numpy()
    
    clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=threshold, 
                                         metric="cosine", linkage='complete')
    labels = clustering.fit_predict(distances_cpu)
    
    unique_labels = np.unique(labels)
    speaker_segments = [[] for _ in range(len(unique_labels))]
    for i, label in enumerate(labels):
        speaker_segments[label].append(i)
    
    return speaker_segments, len(segments)

if __name__ == "__main__":
    audio_file = "data/converted_type.wav"  # 오디오 파일 경로를 지정하세요
    
    if os.path.exists(audio_file):
        speaker_segments, total_segments = distinguish_speakers_in_file(audio_file)

        print(f"총 {len(speaker_segments)}명의 서로 다른 화자가 감지되었습니다.")
        for i, segments in enumerate(speaker_segments, 1):
            start_times = [seg * 5 for seg in segments]  # 5초 세그먼트 기준
            print(f"화자 {i}: 세그먼트 {segments}")
            print(f"   시작 시간(초): {start_times}")
        
        print(f"\n전체 세그먼트 수: {total_segments}")
    else:
        print("오디오 파일을 찾을 수 없습니다.")