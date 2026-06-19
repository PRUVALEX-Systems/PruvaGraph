import sys
import base64

try:
    with open('icon.png', 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    with open('icon_b64.txt', 'w') as f:
        f.write(b64)
    print("Successfully encoded icon.png to icon_b64.txt")
except Exception as e:
    print(f"Error: {e}")
