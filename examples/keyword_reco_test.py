import speech_recognition as sr

def detect_keyword_offline(keyword="hello"):
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Listening for keyword...")
        
        while True:
            try:
                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                text = recognizer.recognize_sphinx(audio).lower()
                print(f"Heard: {text}")
                
                if keyword in text:
                    print("Keyword detected!")
                    # Trigger your action here
                    break
                    
            except sr.UnknownValueError:
                continue
            except sr.WaitTimeoutError:
                continue

detect_keyword_offline("start")