#!/bin/bash

pydep=evdev psutils

echo -ne '[ .... ] Enabling the uinput module\r'
echo uinput >> /etc/modules && echo '[ DONE ]'

echo -ne '[ .... ] Installing python3\r'
apt-get install python3 python3-pip -qq && echo '[ DONE ]'

echo -ne '[ .... ] Installing required python modules\r'
pip3 install -Uqqq $pydep || echo Please run 'pip3 install $pydep' manually
echo '[ DONE ]'

echo -ne '[ .... ] Creating init script\r'
cat touchd-head > /etc/init.d/pytouchd || exit 3
echo "path='$(readlink -f touchd.py)'" >> /etc/init.d/pytouchd || exit 4
cat touchd-tail >> /etc/init.d/pytouchd || exit 5
echo '[ DONE ]'

echo -ne '[ .... ] Making script executable\r'
chmod a+x /etc/init.d/pytouchd && echo '[ DONE ]'

echo -ne '[ .... ] running update-rc.d\r'
update-rc.d pytouchd defaults && echo '[ DONE ]'

echo -ne '[ .... ] Making link /usr/bin/pytouchd\r'
ln -T odroid-vu7+/pytouchd/touchd.py /usr/bin/pytouchd && echo '[ DONE ]'

echo -ne '[ .... ] Rebooting'
sleep 3
reboot
