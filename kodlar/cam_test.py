import cv2


def open_camera():
    # Kameray? aç (0: varsay?lan kamera, 1: harici kamera vb.)
    cap = cv2.VideoCapture(-1)

    if not cap.isOpened():
        print("Kamera aç?lamad?!")
        return

    print("Kamera 'q'  basarak.")
    while True:
        
        ret, frame = cap.read()

        if not ret:
            print("Görüntü alınamadı, çıkılıyor.")
            break


        cv2.imshow("Kamera", frame)

        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    
    cap.release()
    cv2.destroyAllWindows()
    
open_camera()