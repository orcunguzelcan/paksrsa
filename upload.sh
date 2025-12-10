#!/bin/bash
#sudo ncftpput -R -u rsa -p qw34qw34 -P 21 192.168.1.11 "/" "/home/pi/Desktop/PAKS/FTP/Yedekler/"
sudo ncftpput -R -u rsa -p qw34qw34 -P 21 192.168.1.11 "/" "/home/pi/Desktop/PAKS/FTP/Yedekler/" > /home/pi/Desktop/ncftpput.log 2>&1
