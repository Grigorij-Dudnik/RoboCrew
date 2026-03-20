import pygame
import sys

# Import kontrolera sprzętowego
from robocrew.robots.XLeRobot.servo_controls import ServoControler

print("Inicjalizacja sprzętu...")
try:
    ctrl = ServoControler("/dev/arm_right")
    print("Sprzęt gotowy!")
except Exception as e:
    print(f"Błąd inicjalizacji sprzętu: {e}")
    sys.exit(1)

# --- Funkcja pomocnicza do wysyłania komend prędkości ---
def set_continuous_action(controller, action_name):
    """Wysyła stałą prędkość do kół bez ich zatrzymywania."""
    if action_name == "stop":
        controller._wheels_stop()
    else:
        # Pobieramy mnożniki dla danego kierunku z ACTION_MAP
        multipliers = controller.action_map[action_name]
        # Obliczamy prędkość dla każdego koła (ID: 7, 8, 9)
        payload = {wid: int(controller.speed * factor) for wid, factor in multipliers.items()}
        # Wysyłamy komendę bezpośrednio do sterownika
        controller.wheel_bus.sync_write("Goal_Velocity", payload)

# --- Inicjalizacja Pygame ---
pygame.init()
WIDTH, HEIGHT = 450, 350
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("RoboCrew - Płynne Sterowanie")
font = pygame.font.SysFont(None, 24)
clock = pygame.time.Clock()

def draw_interface(status="Zatrzymany"):
    screen.fill((30, 30, 30))
    instructions = [
        "PŁYNNE STEROWANIE:",
        "[↑] - Do przodu    [↓] - Do tyłu",
        "[←] - Obrót lewo   [→] - Obrót prawo",
        "[Q] - Krok w lewo  [E] - Krok w prawo",  # Dodałem strafing!
        "",
        "[ESC] - Wyjście"
    ]
    for i, text in enumerate(instructions):
        img = font.render(text, True, (200, 200, 200))
        screen.blit(img, (20, 20 + (i * 30)))
        
    status_color = (255, 100, 100) if status == "stop" else (100, 255, 100)
    status_img = font.render(f"Akcja robota: {status.upper()}", True, status_color)
    screen.blit(status_img, (20, HEIGHT - 40))
    pygame.display.flip()

running = True
current_state = "stop"
print("Aplikacja uruchomiona. Wybierz okno Pygame i trzymaj strzałki.")

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # Sprawdzanie aktualnie wciśniętych klawiszy
    keys = pygame.key.get_pressed()
    
    desired_state = "stop"
    
    # Mapowanie klawiszy na akcje z pliku servo_controls.py
    if keys[pygame.K_UP]:
        desired_state = "forward"
    elif keys[pygame.K_DOWN]:
        desired_state = "backward"
    elif keys[pygame.K_LEFT]:
        desired_state = "turn_left"
    elif keys[pygame.K_RIGHT]:
        desired_state = "turn_right"
    # Ekstra: wykorzystałem strafe_left / strafe_right z Twojego ACTION_MAP!
    elif keys[pygame.K_q]:
        desired_state = "strafe_left"
    elif keys[pygame.K_e]:
        desired_state = "strafe_right"

    # WYSYŁAMY KOMENDĘ TYLKO GDY ZMIENIA SIĘ STAN (aby nie zapchać magistrali UART)
    if desired_state != current_state:
        set_continuous_action(ctrl, desired_state)
        current_state = desired_state
        draw_interface(current_state)

    clock.tick(30)

# Bezpieczne zatrzymanie przed wyjściem
print("Zamykanie i zatrzymywanie silników...")
ctrl.disconnect()
pygame.quit()
sys.exit()
