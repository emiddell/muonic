from Skyview import *

sk=Skyview()

sk.setup_channel(ch0=True, ch1=True, ch2=True, ch3=True, coincidence='threefold')

sk.set_threashold(th_0=110, th_1=110, th_2=180, th_3=110)

sk.measure_rates(timewindow=10.0, meastime=1.0)