import cv2
import numpy as np
import mediapipe as mp
import json
import os
import math
from datetime import datetime
import base64

class MediaPipeFaceRecognition:
    def __init__(self, data_file='face_data.json'):
        self.data_file = data_file
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Initialize Face Mesh with good settings for detection
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Key facial landmarks for comparison (similar to finger tips)
        # These are stable landmarks that are less affected by expressions
        self.KEY_LANDMARKS = [
            1,    # nose tip
            33,   # left eye corner
            133,  # left eye outer
            362,  # right eye corner
            263,  # right eye outer
            61,   # left mouth corner
            291,  # right mouth corner
            13,   # left eyebrow inner
            14,   # right eyebrow inner
            54,   # left eyebrow outer
            284,  # right eyebrow outer
            10,   # chin
            152,  # jaw
            234,  # left cheek
            454,  # right cheek
            168,  # between eyes
            6,    # left eye inner
            359   # right eye inner
        ]

        # Load existing data
        self.load_data()

    def load_data(self):
        """Load face data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.face_data = json.load(f)
            except:
                self.face_data = {}
        else:
            self.face_data = {}

    def save_data(self):
        """Save face data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.face_data, f, indent=2)

    def extract_face_landmarks(self, image):
        """Extract facial landmarks using MediaPipe"""
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Process the image
        results = self.face_mesh.process(image_rgb)

        if not results.multi_face_landmarks:
            return None, None

        # Get landmarks for the first face
        face_landmarks = results.multi_face_landmarks[0]

        # Extract all landmarks
        landmarks = []
        for landmark in face_landmarks.landmark:
            landmarks.append({
                'x': landmark.x,
                'y': landmark.y,
                'z': landmark.z
            })

        return landmarks, face_landmarks

    def extract_key_landmarks(self, landmarks):
        """Extract only key landmarks for comparison (similar to finger tips)"""
        if not landmarks:
            return None

        key_points = []
        for idx in self.KEY_LANDMARKS:
            if idx < len(landmarks):
                key_points.append(landmarks[idx])

        return key_points

    def compare_face_positions(self, user_landmarks, saved_landmarks, threshold=0.08):
        """Compare key landmark positions (similar to finger tip comparison)"""
        user_key = self.extract_key_landmarks(user_landmarks)
        saved_key = self.extract_key_landmarks(saved_landmarks)

        if not user_key or not saved_key:
            return False, 0

        total_distance = 0
        for i in range(min(len(user_key), len(saved_key))):
            dist = math.sqrt(
                (user_key[i]['x'] - saved_key[i]['x'])**2 +
                (user_key[i]['y'] - saved_key[i]['y'])**2 +
                (user_key[i]['z'] - saved_key[i]['z'])**2
            )
            total_distance += dist

        avg_distance = total_distance / len(user_key)
        is_match = avg_distance < threshold

        # Convert distance to confidence score (0-1)
        confidence = max(0, min(1, 1 - (avg_distance / threshold)))

        return is_match, confidence

    def enroll_face(self, user_id, image_data=None, image_path=None):
        """Enroll a face with multiple samples"""
        # Load image
        if image_path:
            image = cv2.imread(image_path)
        elif image_data:
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return {'success': False, 'message': 'No image provided'}

        if image is None:
            return {'success': False, 'message': 'Could not load image'}

        # Extract landmarks
        landmarks, face_landmarks = self.extract_face_landmarks(image)
        if landmarks is None:
            return {'success': False, 'message': 'No face detected in image. Please ensure good lighting and look directly at camera.'}

        # Check if enough landmarks were detected
        if len(landmarks) < 100:
            return {'success': False, 'message': f'Only {len(landmarks)} landmarks detected. Need at least 100. Please try again with better lighting.'}

        # Initialize user data if not exists
        if user_id not in self.face_data:
            self.face_data[user_id] = []

        # Create face template with key landmarks only (for efficient storage)
        key_landmarks = self.extract_key_landmarks(landmarks)

        face_template = {
            'user_id': user_id,
            'enrolled_at': datetime.now().isoformat(),
            'key_landmarks': key_landmarks,  # Store only key landmarks (similar to gesture data)
            'num_landmarks': len(landmarks),
            'confidence': 0
        }

        self.face_data[user_id].append(face_template)

        # Keep only last 10 templates (limit storage)
        if len(self.face_data[user_id]) > 10:
            self.face_data[user_id] = self.face_data[user_id][-10:]

        self.save_data()

        # Save preview image
        preview_path = f'face_data/{user_id}_preview_{len(self.face_data[user_id])}.jpg'
        os.makedirs('face_data', exist_ok=True)

        # Draw face mesh on image for preview
        annotated_image = self.draw_face_mesh(image, face_landmarks)
        cv2.imwrite(preview_path, annotated_image)

        return {
            'success': True,
            'message': f'Face enrolled successfully! Detected {len(landmarks)} landmarks. Template #{len(self.face_data[user_id])}',
            'num_templates': len(self.face_data[user_id]),
            'preview_path': preview_path
        }

    def verify_face(self, user_id, image_data=None, image_path=None, threshold=0.65):
        """Verify a face against enrolled templates (similar to gesture matching)"""
        # Load image
        if image_path:
            image = cv2.imread(image_path)
        elif image_data:
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return {'success': False, 'message': 'No image provided', 'verified': False}

        if image is None:
            return {'success': False, 'message': 'Could not load image', 'verified': False}

        # Check if user has enrolled faces
        if user_id not in self.face_data or not self.face_data[user_id]:
            return {'success': False, 'message': 'No face templates found. Please setup face recognition first.', 'verified': False}

        # Extract landmarks from verification image
        landmarks, face_landmarks = self.extract_face_landmarks(image)
        if landmarks is None:
            return {'success': False, 'message': 'No face detected. Please look directly at camera with good lighting.', 'verified': False}

        # Compare with stored templates (similar to gesture matching)
        best_match_score = 0
        best_match_index = -1
        all_scores = []

        for idx, template in enumerate(self.face_data[user_id]):
            saved_key_landmarks = template.get('key_landmarks')
            if saved_key_landmarks:
                is_match, confidence = self.compare_face_positions(landmarks, saved_key_landmarks, threshold)
                all_scores.append(confidence)

                if confidence > best_match_score:
                    best_match_score = confidence
                    best_match_index = idx

        verified = best_match_score >= threshold

        return {
            'success': True,
            'verified': verified,
            'confidence': float(best_match_score),
            'threshold': threshold,
            'message': 'Face verified successfully!' if verified else f'Face verification failed. Best match: {int(best_match_score * 100)}%',
            'template_used': best_match_index,
            'all_scores': all_scores,
            'num_templates': len(self.face_data[user_id])
        }

    def draw_face_mesh(self, image, face_landmarks):
        """Draw the face mesh with key points highlighted"""
        annotated_image = image.copy()

        # Draw the face mesh
        self.mp_drawing.draw_landmarks(
            image=annotated_image,
            landmark_list=face_landmarks,
            connections=self.mp_face_mesh.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=self.mp_drawing_styles
            .get_default_face_mesh_tesselation_style()
        )

        # Draw key landmarks in different color for emphasis
        h, w = annotated_image.shape[:2]
        for idx in self.KEY_LANDMARKS:
            if idx < len(face_landmarks.landmark):
                landmark = face_landmarks.landmark[idx]
                cx, cy = int(landmark.x * w), int(landmark.y * h)
                cv2.circle(annotated_image, (cx, cy), 3, (0, 255, 255), -1)

        return annotated_image

    def get_face_preview(self, user_id):
        """Get the preview image with face mesh for a user"""
        if user_id in self.face_data and self.face_data[user_id]:
            # Return the most recent preview
            preview_path = f'face_data/{user_id}_preview_{len(self.face_data[user_id])}.jpg'
            if os.path.exists(preview_path):
                with open(preview_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode()
        return None

    def delete_face_data(self, user_id):
        """Delete all face data for a user"""
        if user_id in self.face_data:
            # Delete preview images
            for i in range(1, len(self.face_data[user_id]) + 1):
                preview_path = f'face_data/{user_id}_preview_{i}.jpg'
                if os.path.exists(preview_path):
                    os.remove(preview_path)

            del self.face_data[user_id]
            self.save_data()
            return {'success': True, 'message': 'Face data deleted successfully'}

        return {'success': False, 'message': 'No face data found'}

    def get_face_info(self, user_id):
        """Get information about enrolled faces"""
        if user_id not in self.face_data or not self.face_data[user_id]:
            return {'success': False, 'templates': 0, 'has_data': False}

        templates = self.face_data[user_id]

        return {
            'success': True,
            'templates': len(templates),
            'has_data': True,
            'enrolled_at': [t.get('enrolled_at', 'Unknown') for t in templates],
            'landmarks_per_template': [t.get('num_landmarks', 468) for t in templates]
        }

# Initialize global instance
face_system = MediaPipeFaceRecognition('face_data.json')
