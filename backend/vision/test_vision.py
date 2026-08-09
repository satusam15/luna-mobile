from vision.vision_service import VisionService

vision = VisionService()

result = vision.describe("screenshot.png")

print(result)