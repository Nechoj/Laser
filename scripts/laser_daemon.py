#!/usr/bin/python
# This script is started as a background process by shell skript /etc/init.d/laser_daemon.sh
# The lasers are managed and move commands are executed
# communication with php-pages is via database table Parameters
import sys
import time
import os
import signal
import RPi.GPIO as GPIO
#sys.path.append('/home/pi/www/scripts/') # only needed if this script is not located in the same directory as CVision.py ...
from CVision import *


class App():
    def __init__(self):
        # store kill command with PID in a shell skript
        tmpfile = "/tmp/laser_daemon_stop"
        PID = os.getpid()  
        try:
            fd = os.open(tmpfile,os.O_RDWR|os.O_CREAT)
        except:
            print "Error in App::__init__:: could not open file"
            sys.exit(1)        
        os.write(fd,"#! /bin/sh\n")
        os.write(fd,''.join(["kill -s INT ", str(PID), "\n"]))
        os.close(fd)
        
        try:
            self.C = Calibration()
        except:
            print "Error in App::__init__: "
            sys.exit(1)
            
        self.C.LM.SetBeamWidth(10)
        
        # initialising parameters
        self.C.P.StoreParameter("Action", "done", "string")
        self.C.P.StoreParameter("L_xy", "1000", "string")
        self.C.P.StoreParameter("L_rcm", "1000", "string")
        self.C.P.StoreParameter("dist_x","0","integer")
        self.C.P.StoreParameter("dist_y","0","integer")
        self.C.P.StoreParameter("row","0","integer")
        
        # this flag is set by the signal handler
        self.shutdownflag = False
        
        # variables for time-out handling of the laser
        self.LaserIsOn = False
        self.TimeOut = 6 # in seconds
        self.LaserStartTime = 0
        
        # initialise GPIOs
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(7, GPIO.OUT)
        GPIO.output(7, GPIO.HIGH) # HIGH = laser is off
        
        print "init done"
        
    def handler(self, signum, frame):
        print 'Signal handler called with signal', signum
        self.shutdownflag = True
        
    def LaserOn(self):
        if not self.LaserIsOn: # switch laser on if necessary
            self.LaserStartTime = time.time()
            GPIO.output(7, GPIO.LOW)
            self.LaserIsOn = True            
            print "laser on"
            time.sleep(2) # wait for the laser to power up
        else:
            self.LaserStartTime = time.time() # reset LaserStartTime
            
    def run(self):
            while True: # run until shutdownflag is True
            
                pAction = self.C.P.GetParameter("Action")
            
                if pAction == "Move_xy":
                    self.LaserOn()
                    pL_xy = self.C.P.GetParameter("L_xy")
                    if pL_xy != None:
                        Ly = pL_xy%1000
                        Lx = (pL_xy - Ly)/1000
                        self.C.LM.Move(Lx,Ly)
                        print "moved_xy", Lx, Ly
                    self.C.P.SetParameter("Action", "done")
            
                elif pAction == "Move_rcm":
                    self.LaserOn()
                    pL_rcm = self.C.P.GetParameter("L_rcm")
                    if pL_rcm != None:
                        cm = pL_rcm%1000
                        row = (pL_rcm - cm)/1000
                        self.C.LM.MoveCM(cm,0,row)
                        print "moved_rcm", row, cm
                    self.C.P.SetParameter("Action", "done")
        
                elif pAction == "Stop":
                    self.C.LM.Stop()
                    print "stopped"
                    self.C.P.SetParameter("Action", "done")  
                
                elif pAction == "Detect1":
                    self.LaserOn()
                    dist_x, dist_y, row = self.C.DetectMissingBook(1)
                    print "Step 1 completed"
                    self.C.P.SetParameter("Action", "done")

                
                elif pAction == "Detect2":
                    self.LaserOn()
                    dist_x, dist_y, row = self.C.DetectMissingBook(2)
                    if dist_x!=None and dist_y!=None:
                        print dist_x, dist_y, row
                        self.C.LM.MoveCM(dist_x, dist_y, row)
                        self.C.P.SetParameter("dist_x",str(dist_x))
                        self.C.P.SetParameter("dist_y",str(dist_y))
                        self.C.P.SetParameter("row",str(row))
                    else:
                        self.C.P.SetParameter("dist_x","0")
                        self.C.P.SetParameter("dist_y","0")
                        self.C.P.SetParameter("row","0")                        
                    print "Step 2 completed"
                    self.C.P.SetParameter("Action", "done") 

            
                else:
                    # if laser is on and time-out has come switch it off
                    if self.LaserIsOn:
                        t_diff = time.time() - self.LaserStartTime
                        if t_diff > self.TimeOut:
                            GPIO.output(7, GPIO.HIGH)
                            self.LaserIsOn = False
                            print "laser off"
                        
                    if self.shutdownflag:
                        print "shutting down process ..."
                        self.C.Cam.Close()
                        if os.path.isfile(self.tmpfile):
                            os.remove(self.tmpfile)
                        sys.exit(0)
                
                time.sleep(0.4)


app = App()
signal.signal(signal.SIGINT, app.handler)
signal.signal(signal.SIGHUP, app.handler)
app.run()




        
