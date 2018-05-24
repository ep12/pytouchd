# pytouchd
Python driver for some touch screens like the ODROID VU7+ etc.

# History
After googling around it seems to be harder than it should to get the touch functionality
of some touch displays working. In the initial case, the ODROID VU7+ screen with the
Raspberry Pi 3 SBC works perfectly fine as a display but without input. Compiling a new
kernel that can handle the different type of input was too much work for such a small
thing. In a post concerning that problem (VU7+ and RPI3) it was stated that the current
support for other monitors should be kept and my idea was that it is possible to write a
driver that is capable of handling both types of input since only two tiny details have
chainged:
1. In the original struct, every coordinate is one byte. So a point (x, y) is two bytes in
length. If you have a display with a 4K resolution (3840 x 2160), many different input
presses on different pixels will appear with the same two bytes. In that example, a touch
in a 15x8 pixels area is quite a big of an error. My VU7+ sends two bytes instead of one
for each coordinate. That means, the touch resolution is way better! (65536 instead of 256
display parts for each axis.)
2. The mode is not limited to be relative (0 = 0%, 255 = 100%), the exact absolute pixel
coordinate is sent!

This driver is a (proof of) concept for a universal driver as described above. If the
driver detects that a point (2 coordinates) consists of 2 bytes (bpc (bytes per coordinate)
is 1), the mode is set to relative, for bpc==2 the absolute mode is chosen.

If you want to, you can adapt this idea, especially if you are working on the kernel that
should be handling touch input!

# Tests
touch device               | SBC                               | status
---------------------------|-----------------------------------|-------------------------
ODROID VU7+                | RasPi3                            | beta, dblClick not good

# Installation

1. Always load the UInput module:
	```sh
	sudo echo uinput >> /etc/modules
	```
2. Install python3 and dependencies:
	```sh
	sudo apt-get install python3 python3-pip
	# try with sudo if it doesn't work (I have strange errors, but it works perfectly as root ?_?)
	pip3 install -U numpy evdev
	```
3. Clone this repo
4. Install start-up script
TODO

# Options

name                    | type   | default value | comment
------------------------|--------|---------------|---------------------------------------------------------------------
live                    | bool   | false         | disable all enhancements and foward the raw input
dblClickTime            | float  |               | if a click is registered within x seconds after the last click has begun and the new position is within the dragDist radius, the DBL mode is set.
holdForRightClick       | bool   | true          | perform a right click when pressing the touch screen for longClickTime seconds
longClickTime           | float  |               | in seconds
dragDist                | custom |               | defines the distance that must be exceeded to start a drag. In px, in, cm, mm if devW and devH are given, else: pixels
devW, devH              | custom |               | the phyical measurements of the touch area in cm, mm, in
