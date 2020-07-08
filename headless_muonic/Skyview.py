import logging
from muonic import daq
from datetime import datetime
from time import sleep, time
import Queue
import threading

class Skyview():

	def __init__(self):

		#needed for process_incoming
		self.countqueue=Queue.Queue()
		self.tempqueue=Queue.Queue()
		self.pressqueue=Queue.Queue()
		self.dataqueue=Queue.Queue()

		self.running=False
		#maximum number of the scalers on the DAQ board
		self.max_counts= int("FFFFFFFF", 16)

		#setup logger
		self.logger = logging.getLogger()
		self.logger.setLevel(logging.DEBUG)
		ch = logging.StreamHandler()
		ch.setLevel(logging.DEBUG)
		formatter = logging.Formatter('%(levelname)s:%(process)d:%(module)s:%(funcName)s:%(lineno)d:%(message)s')
		ch.setFormatter(formatter)
		self.logger.addHandler(ch)

		# setup connection to QuarkNET card, enable communication
		self.client = daq.DAQProvider(logger=self.logger)

		#disable data flow for startup
		self.stop_reading_data()
		#disable status message
		self.do('ST 0')

		

	def do(self, msg):
		"""
		Send command to DAQ card and remove repeated response from the outqueue
		if data taking is turned off. Otherwise just send command to DAQ card. 
		"""
		if self.running==False:
			self.client.put(msg)
			sleep(0.5)
			self.client.get(0)
			if msg=='ST 0' or msg.startswith('WC'):
				self.client.get(0)
		else:
			self.client.put(msg)



	def reset_scalars(self):
		"""
		Reset the scalars of all channels.
		"""
		self.do('RB')
		self.logger.debug('Resetted scalars.')


	def start_reading_data(self):
		"""
		Start receiving data from the DAQ card and storing it in self.dataqueue.
		"""
		self.logger.debug('Start reading data into queues.')
		self.do('CE')
		self.process_incoming()


	def stop_reading_data(self):
		"""
		Stop receiving data from the DAQ card.
		"""
		self.do('CD')
		while self.client.data_available():
			self.client.get(0)
		self.logger.debug('Stopped reading data.')


	def read_scalars(self):
		"""
		Read the scalars of all channels.
		If no measurement is running, returns scalar values: ch0, ch1, ch2, ch3, trigger
		"""
		if self.running:
			self.client.put('DS')
		else:
			self.do('DS')
			scalar_msg=self.client.get(0)
			if scalar_msg.startswith('DS'):
				self.get_scalars(scalar_msg)
				return self.counts_ch0, self.counts_ch1, self.counts_ch2, self.counts_ch3, self.counts_trigger
			else:
				self.logger.info("Didn't find scalars in message. %s" % scalar_msg)



	def set_threashold(self, th_0=300, th_1=300, th_2=300, th_3=300):
		"""
		Set the threasholds for the channels of the DAQ card.
		Default value for all channels is 300.
		"""
		Th=[th_0, th_1, th_2, th_3]
		for i in range(4):
			msg="TL "+str(i)+" "+str(Th[i])
			self.do(msg)

		self.do('TL')
		scan=0
		while scan < 10:
			response_th=self.client.get(0)
			if response_th.startswith('TL') and len(response_th)>9:
				self.logger.info("Thresholds set to %s" % response_th)
				break
			else:
				self.logger.debug("Haven't found threasholds yet")
				self.logger.debug(response_th)
				scan+=1
		else:
			self.logger.error("Didn't find threashold setting in last 10 messanges coming from DAQ card. Something is wrong!")

	

	def setup_channel(self, ch0=False, ch1=False, ch2=False, ch3=False, coincidence='single'):
		"""
		Enable/Disable channels of the DAQ card and set coincidence settings.
		"""
		self.nchannels=0
		channels=[ch3, ch2, ch1, ch0]
		ch_setting=str("")
		for i in range(4):
			if channels[i]==False:
				ch_setting+='0'
			elif channels[i]==True:
				ch_setting+='1'
				self.nchannels+=1
		ch=format(int(ch_setting,2),'X')

		if coincidence=='single':
			coinc=0
		elif coincidence=='twofold':
			coinc=1
		elif coincidence=='threefold':
			coinc=2
		elif coincidence=='fourfold':
			coinc=3

		msg="WC 00 "+str(coinc)+str(ch)
		self.do(msg)
		sleep(0.5)
		self.do('DC')
		response_ch=self.client.get(0)
		self.logger.info("Channels set. %s" % response_ch)



	def get_temp_and_pressure(self):
		"""
		Read out temperature and pressure data.
		Pressure data in unit counts and mBar.  
		If no measurement is running returns temperature, pressure, pressure_mbar
		"""
		self.temperature=-999.0
		self.pressure=-999.0
		self.pressure_mbar=-999.0

		if self.running:
			#get temperature from temperature queue
			if self.tempqueue.qsize():
				msg_temp=self.tempqueue.get(0)
				self.temperature=float(msg_temp.split("=")[1])
			else:
				self.logger.info("Failed to measure the temperature. No element in queue.")

			#get pressure from pressure queue
			if self.pressqueue.qsize():
				msg_press=self.pressqueue.get(0)
				msg_press_mbar=self.pressqueue.get(0)
				self.check_pressure_msg(msg_press)
				self.check_pressure_msg(msg_press_mbar)
			else:
				self.logger.info("Failed to measure the pressure. No element in queue.")

		else:
			self.do('TH')
			msg_temp=self.client.get(0)
			if msg_temp.startswith('TH'):
				self.temperature=float(msg_temp.split("=")[1])
				self.logger.debug('Measured temperature: %f' % self.temperature)
			else:
				self.logger.error("Could not read temperature.")
			self.do('BA')
			msg_press=self.client.get(0)
			if msg_press.startswith('BA'):
				self.pressure=float(msg_press.split()[1])
				self.logger.debug('Measured pressure: %f' % self.pressure)
			else:
				self.logger.error("Could not read pressure [counts].")
			#take out the 'calibrate pressure' message:
			self.client.get(0)

			calib_press=self.client.get(0)
			if calib_press.startswith('mBar'):
				self.pressure_mbar=float(calib_press.split()[4])
				self.logger.debug('Measured pressure in mBar: %f' % self.pressure_mbar)
			else:
				self.logger.error("Could not read pressure [mBar].")

			return self.temperature, self.pressure, self.pressure_mbar



	def check_pressure_msg(self, msg):
		"""
		Check message for pressure information. 
		"""
		if msg.startswith('BA'):
			self.pressure=float(msg.split()[1])
		elif msg.startswith('mBar'):
			self.pressure_mbar=float(msg.split()[4])
		else:
			self.logger.info("Weird element in pressure queue. Could not read pressure.")



	def get_gps_info(self):
		self.do('DG')
		Found=False
		msg=self.client.get(0)
		while not Found:
			if msg.startswith('Date+Time'):
				gpsmsg=msg
				Found=True
			else:
				msg=self.client.get(0)


		GPSDateTime=gpsmsg
		Status=self.client.get(0)
		PosFix=self.client.get(0)
		Latitude=self.client.get(0)
		Longitude=self.client.get(0)
		Altitude=self.client.get(0)
		NSats=self.client.get(0)
		PPSDelay=self.client.get(0)
		FPGATime=self.client.get(0)
		ChkSumErr=self.client.get(0)

		self.logger.info(GPSDateTime)
		self.logger.info(Status)
		self.logger.info(PosFix)
		self.logger.info(Latitude)
		self.logger.info(Longitude)
		self.logger.info(Altitude)
		self.logger.info(NSats)
		self.logger.info(PPSDelay)
		self.logger.info(FPGATime)
		self.logger.info(ChkSumErr)



	def process_incoming(self):
		"""
		Sort messages received from the DAQ card and store them in separate queues.
		"""
		while self.running:
			while self.client.data_available():
				try:
					msg=self.client.get(0)
				except:
					self.logger.debug('Queue empty!')
					break
				#print(msg)
				if msg.startswith('DS'):
					if len(msg)>=3:
						self.countqueue.put(msg)
				elif msg.startswith('TH'):
					if len(msg)>=9:
						self.tempqueue.put(msg)
				elif msg.startswith('BA') or msg.startswith('mBar'):
					if len(msg)>=4:
						self.pressqueue.put(msg)
				elif msg.startswith('CD') or msg.startswith('CE'):
					continue
				else:
					self.dataqueue.put(msg)
			else:
				sleep(0.2)



	def get_scalars(self, msg=None):
		"""
		If running=True, read out scalars from the counterqueue. 
		Otherwise, read scalars from given message. 
		Returns the scalar values.
		"""
		if msg!=None:
			counter_from_msg=msg.split()
		else:
			if self.countqueue.qsize():
				count_msg=self.countqueue.get(0)
				counter_from_msg=count_msg.split()
			else:
				self.logger.error("Failed to get counters. No element in queue.")

		for item in counter_from_msg:
			if ("S0" in item) & (len(item) == 11):
				self.counts_ch0 = int(item[3:],16)
			elif ("S1" in item) & (len(item) == 11):
				self.counts_ch1 = int(item[3:],16)
			elif ("S2" in item) & (len(item) == 11):
				self.counts_ch2 = int(item[3:],16)
			elif ("S3" in item) & (len(item) == 11):
				self.counts_ch3 = int(item[3:],16)
			elif ("S4" in item) & (len(item) == 11):
				self.counts_trigger = int(item[3:],16)
			elif ("S5" in item) & (len(item) == 11):
				counters_time = float(int(item[3:],16))

		return self.counts_ch0, self.counts_ch1, self.counts_ch2, self.counts_ch3, self.counts_trigger



	def calculate_rates(self):
		"""
		Calculate rates during rate measurements. 
		"""
		counts_ch0_start, counts_ch1_start, counts_ch2_start, counts_ch3_start, counts_trigger_start = self.get_scalars()
		counts_ch0_end, counts_ch1_end, counts_ch2_end, counts_ch3_end, counts_trigger_end = self.get_scalars()

		counters_previous = [counts_ch0_start, counts_ch1_start, counts_ch2_start, counts_ch3_start, counts_trigger_start]
		counters = [counts_ch0_end, counts_ch1_end, counts_ch2_end, counts_ch3_end, counts_trigger_end]

		self.diff_counters=[]
		self.rates=[]

		for i in range(len(counters)):
			if counters[i]>=counters_previous[i]:
				self.diff_counters.append(counters[i]-counters_previous[i])
			elif counters[i] < counters_previous[i]:
				self.diff_counters.append(max_counts-counters_previous[i]+counters[i])
			self.rates.append(self.diff_counters[i]/self.delta_time)



	def clear_queues(self):
		"""
		Clear all the queues filled in process_incoming().
		"""
		for queue in [self.countqueue, self.pressqueue, self.tempqueue, self.dataqueue]:
			while queue.qsize():
				queue.get(0)
		self.logger.debug('Finished clearing queues.')



	def write_rates_to_file(self, filename='', firstline=False):
		"""
		Saves data to file during rate measurements.
		"""
		with open(filename, 'a') as f:
			if firstline:
				self.logger.info('Starting to write data to file %s' % filename)
				f.write(" date | time | R0 | R1 | R2 | R3 | R_trigger | chan0 | chan1 | chan2 | chan3 | trigger | Delta_time | Pressure [mBar] | Temperature [C] \n")
			else:
				f.write("%s %f %f %f %f %f %f %f %f %f %f %f %f %f \n" % (self.dateandtime,\
																		self.rates[0],\
																		self.rates[1],\
																		self.rates[2],\
																		self.rates[3],\
																		self.rates[4],\
																		self.counts_ch0,\
																		self.counts_ch1,\
																		self.counts_ch2,\
																		self.counts_ch3,\
																		self.counts_trigger,\
																		self.delta_time,\
																		self.pressure_mbar,\
																		self.temperature))



	def measure_rates(self, timewindow=5.0, meastime=None):
		"""
		Measure rates seen by the counters.
		:param timewindow: Time between successive rate measurements in seconds. Default is 5 seconds.
		:param meastime: Total measurement time in minutes. Default is None.
		"""
		if isinstance(meastime, float):
			self.logger.info('Starting rate measurement. Rate is measured every %f seconds, total measurement time: %f min' % (timewindow, meastime))
			self.running=True
			self.starttime=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
			self.write_rates_to_file(filename=self.starttime+"_R.txt", firstline=True)
			self.reset_scalars()
			x=threading.Thread(target=self.start_reading_data)
			x.start()

			t=0
			try:
				while t < (meastime*60):
					self.read_scalars()
					time_start=time()
					sleep(timewindow)
					self.read_scalars()
					time_end=time()
					self.dateandtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
					self.do('TH')
					self.do('BA')
					sleep(0.5)
					self.get_temp_and_pressure()
					self.delta_time=time_end-time_start
					self.calculate_rates()
					self.write_rates_to_file(filename=self.starttime+"_R.txt")
					self.logger.info('Measurement progress: %f %%' % (100*t/(meastime*60)))
					t+=self.delta_time
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False	
				self.logger.info('Measurement stopped!')	
				self.clear_queues()
			except (KeyboardInterrupt, AttributeError, RuntimeError, NameError, SystemExit): 
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False
				self.logger.info('Measurement stopped!')
				self.clear_queues()


		elif meastime==None:
			self.logger.info('Starting rate measurement. Rate is measured every %f seconds. No measurement time set.' % timewindow)
			self.running=True
			self.starttime=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
			self.write_rates_to_file(filename=self.starttime+"_R.txt", firstline=True)
			self.reset_scalars()
			x=threading.Thread(target=self.process_incoming)
			x.start()

			try:
				while self.running:
					self.read_scalars()
					time_start=time()
					sleep(timewindow)
					self.read_scalars()
					time_end=time()
					self.dateandtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
					self.do('TH')
					self.do('BA')
					sleep(0.5)
					self.get_temp_and_pressure()
					self.delta_time=time_end-time_start
					self.calculate_rates()
					self.write_rates_to_file(filename=self.starttime+"_R.txt")
			except (KeyboardInterrupt, AttributeError, RuntimeError, NameError, SystemExit): 
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False
				self.logger.info('Measurement stopped!')
				self.clear_queues()

		else:
			self.logger.error('Got incorrect meastime. If you do not want to specify meastime, set it to None.')




	def measure_pulses(self, meastime=None):
		"""
		Measure pulses (rising and falling edge times) of trigger events. Using PulseExtractor from muonic.
		:param meastime: Total measurement time in minutes. Default is None.
		"""
		from muonic.analysis import PulseExtractor

		if isinstance(meastime, float):
			self.logger.info('Starting pulse measurement. Total measurement time: %f' % meastime)
			if self.running:
				pass
			else:
				self.running=True
				self.starttime=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
				x=threading.Thread(target=self.start_reading_data)
				x.start()

			filename_pulses=self.starttime+"_P.txt"

			pe=PulseExtractor(self.logger, filename_pulses)
			pe.write_pulses(True)

			t=0
			start_t=time()

			try:
				while t < (meastime*60):
					while self.dataqueue.qsize()!=0:
						try:
							msg=self.dataqueue.get()
						except:
							self.logger.debug('Dataqueue empty!')
							break
						pulses=pe.extract(msg)
						t=time()-start_t
						self.logger.info('Measurement progress: %f %%' % (100*t/(meastime*60)))
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False
				self.logger.info('Measurement stopped!')
				self.clear_queues()
			except (KeyboardInterrupt, SystemExit): 
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False
				self.logger.info('Measurement stopped!')
				self.clear_queues()

		elif meastime==None:
			self.logger.info('Starting pulse measurement. No measurement time set.')
			if self.running:
				pass
			else:
				self.running=True
				self.starttime=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
				x=threading.Thread(target=self.start_reading_data)
				x.start()

			filename_pulses=self.starttime+"_P.txt"

			pe=PulseExtractor(self.logger, filename_pulses)
			pe.write_pulses(True)

			try:
				while self.running:
					while self.dataqueue.qsize()!=0:
						try:
							msg=self.dataqueue.get()
						except:
							self.logger.debug('Dataqueue empty!')
							break
						pe.extract(msg)
						
			except (KeyboardInterrupt, SystemExit): 
				self.stop_reading_data()
				self.logger.info('Measurement is stopping. Please wait!')
				sleep(5)
				self.running=False
				self.logger.info('Measurement stopped!')
				self.clear_queues()



