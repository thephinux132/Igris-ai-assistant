# Define a class for a rectangle
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def perimeter(self):
        return 2 * (self.width + self.height)

def main():
    # Create a rectangle with dimensions 5 cm by 3 cm
    rect1 = Rectangle(5, 3)

    # Calculate and print the area of the rectangle
    print("Area of Rect. 5x3cm:", rect1.area())

    # Calculate and print the perimeter of the rectangle
    print("Perimeter of Rect. 5x3cm:", rect1.perimeter())

    # Create a new rectangle with dimensions 8 cm by 4 cm
    rect2 = Rectangle(8, 4)

    # Calculate and print the area of the second rectangle
    print("Area of Rect. 8x4cm:", rect2.area())

    # Calculate and print the perimeter of the second rectangle
    print("Perimeter of Rect. 8x4cm:", rect2.perimeter())

if __name__ == "__main__":
    main()
