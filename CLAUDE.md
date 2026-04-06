# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Face Recognition Access Control System** (人脸识别门禁系统) - a design/planning repository for a face-based entry and attendance tracking system.

## Architecture

The system follows a layered architecture:

1. **Frontend Layer**: Web admin panel, mobile app for user registration
2. **Gateway Layer**: Nginx/Kong for load balancing, SSL termination, routing
3. **Business Service Layer**: User center, device management, attendance records
4. **AI Algorithm Layer**: Face detection, liveness detection, feature extraction & matching
5. **Hardware Control Layer**: Access control board (Raspberry Pi/industrial board), electromagnetic lock controller
6. **Data Layer**: MySQL (user info), Redis (real-time whitelist/tokens), MinIO/object storage (original face images), vector database (face feature vectors - Milvus/Faiss)

## Core Workflows

### Registration Flow
Upload photo → Quality detection → Liveness detection → Feature extraction → Store feature vector & associate with user ID

### Face Scan Flow
Camera capture → Real-time transmission → Face detection → Liveness detection → Feature matching → Send open door command → Log entry

## Key Technology Stack

- **Face Detection**: RetinaFace or YOLO-Face
- **Face Recognition**: ArcFace (industry-leading accuracy)
- **Liveness Detection**: Silent-Face-Anti-spoofing + IR/depth camera hardware
- **Vector Search**: Milvus or Faiss for high-dimensional vector similarity search
- **Backend**: Python (model inference) + Go/Java (business logic)
- **Hardware Communication**: MQTT protocol for IoT device commands

## Security Requirements

- **Transport Encryption**: TLS for video streams and control commands
- **Data Privacy**: Store only feature vectors, not raw images for matching
- **Anti-replay**: Open door commands must include timestamp and signature validation (5-second validity window)

## Database Schema (Core Tables)

- **users**: id, name, face_token, status
- **access_logs**: id, user_id, device_id, action_time, result, confidence, snapshot_url

## Implementation Phases

1. **Prototype**: Use `face_recognition` Python library for demo validation
2. **Hardware Integration**: Relay control circuit debugging
3. **Model Optimization**: IR dual camera for low-light, liveness detection
4. **Stress Testing**: Multi-user continuous face scan simulation

## Language

Documentation and requirements are in Chinese. Implementation code should use English naming conventions.
