def rgb_from_name(name):
    """Create an rgb tuple from a string."""
    xhash = 0
    for char in name:
        xhash = ord(char) + ((xhash << 5) - xhash)
    red = xhash & 255
    green = (xhash >> 8) & 255
    blue = (xhash >> 16) & 255
    return red, green, blue
