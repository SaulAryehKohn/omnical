import datetime
import socket, multiprocessing, math, random, traceback, ephem, string, commands, datetime
import time
from time import ctime
import aipy as ap
import struct
import numpy as np
import os, sys
import datetime
from optparse import OptionParser
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=DeprecationWarning)
    import scipy as sp
    import scipy.sparse as sps
    import scipy.linalg as la

FILENAME = "calibration_omni.py"


infokeys = ['nAntenna','nUBL','nBaseline','subsetant','antloc','subsetbl','ubl','bltoubl','reversed','reversedauto','autoindex','crossindex','bl2d','ublcount','ublindex','bl1dmatrix','degenM','A','B','At','Bt','AtAi','BtBi','AtAiAt','BtBiBt','PA','PB','ImPA','ImPB']

def read_redundantinfo(infopath):
	with open(infopath) as f:
		rawinfo = np.array([np.array([float(x) for x in line.split()]) for line in f])
	METHODNAME = "read_redundantinfo"
	print FILENAME + "*" + METHODNAME + " MSG:",  "Reading redundant info...",

	info = {}
	infocount = 0;
	info['nAntenna'] = int(rawinfo[infocount][0]) #number of good antennas among all (64) antennas, same as the length of subsetant
	infocount += 1

	info['nUBL'] = int(rawinfo[infocount][0]) #number of unique baselines
	infocount += 1

	nbl = int(rawinfo[infocount][0])
	info['nBaseline'] = nbl
	infocount += 1


	info['subsetant'] = rawinfo[infocount].astype(int) #the index of good antennas in all (64) antennas
	infocount += 1

	info['antloc'] = rawinfo[infocount].reshape((info['nAntenna'],3)) #the index of good antennas in all (64) antennas
	infocount += 1

	info['subsetbl'] = rawinfo[infocount].astype(int) #the index of good baselines (auto included) in all baselines
	infocount += 1
	info['ubl'] = rawinfo[infocount].reshape((info['nUBL'],3)) #unique baseline vectors
	infocount += 1
	info['bltoubl'] = rawinfo[infocount].astype(int) #cross bl number to ubl index
	infocount += 1
	info['reversed'] = rawinfo[infocount].astype(int) #cross only bl if reversed -1, otherwise 1
	infocount += 1
	info['reversedauto'] = rawinfo[infocount].astype(int) #the index of good baselines (auto included) in all baselines
	infocount += 1
	info['autoindex'] = rawinfo[infocount].astype(int)  #index of auto bls among good bls
	infocount += 1
	info['crossindex'] = rawinfo[infocount].astype(int)  #index of cross bls among good bls
	infocount += 1
	ncross = len(info['crossindex'])
	info['ncross'] = ncross
	info['bl2d'] = rawinfo[infocount].reshape(nbl, 2).astype(int) #from 1d bl index to a pair of antenna numbers
	infocount += 1
	info['ublcount'] = rawinfo[infocount].astype(int) #for each ubl, the number of good cross bls corresponding to it
	infocount += 1
	info['ublindex'] = range((info['nUBL'])) #//for each ubl, the vector<int> contains (ant1, ant2, crossbl)
	tmp = rawinfo[infocount].reshape(ncross, 3).astype(int)
	infocount += 1
	cnter = 0
	for i in range(info['nUBL']):
		info['ublindex'][i] = np.zeros((info['ublcount'][i],3))
		for j in range(len(info['ublindex'][i])):
			info['ublindex'][i][j] = tmp[cnter]
			cnter+=1


	info['bl1dmatrix'] = rawinfo[infocount].reshape((info['nAntenna'], info['nAntenna'])).astype(int) #a symmetric matrix where col/row numbers are antenna indices and entries are 1d baseline index not counting auto corr
	infocount += 1
	#matrices
	info['degenM'] = rawinfo[infocount].reshape((info['nAntenna'] + info['nUBL'], info['nAntenna']))
	infocount += 1
	info['A'] = sps.csr_matrix(rawinfo[infocount].reshape((ncross, info['nAntenna'] + info['nUBL'])).astype(int)) #A matrix for logcal amplitude
	infocount += 1
	info['B'] = sps.csr_matrix(rawinfo[infocount].reshape((ncross, info['nAntenna'] + info['nUBL'])).astype(int)) #B matrix for logcal phase
	infocount += 1
	##The sparse matrices are treated a little differently because they are not rectangular
	with warnings.catch_warnings():
		warnings.filterwarnings("ignore",category=DeprecationWarning)
		info['At'] = info['A'].transpose()
		info['Bt'] = info['B'].transpose()
		info['AtAi'] = la.pinv(info['At'].dot(info['A']).todense())#(AtA)^-1
		info['BtBi'] = la.pinv(info['Bt'].dot(info['B']).todense())#(BtB)^-1
		info['AtAiAt'] = info['AtAi'].dot(info['At'].todense())#(AtA)^-1At
		info['BtBiBt'] = info['BtBi'].dot(info['Bt'].todense())#(BtB)^-1Bt
		info['PA'] = info['A'].dot(info['AtAiAt'])#A(AtA)^-1At
		info['PB'] = info['B'].dot(info['BtBiBt'])#B(BtB)^-1Bt
		info['ImPA'] = sps.identity(ncross) - info['PA']#I-PA
		info['ImPB'] = sps.identity(ncross) - info['PB']#I-PB
	print "done. nAntenna, nUBL, nBaseline = ", len(info['subsetant']), info['nUBL'], info['nBaseline']
	return info


def write_redundantinfo(info, infopath, overwrite = False):
	METHODNAME = "*write_redundantinfo*"
	if (not overwrite) and os.path.isfile(infopath):
		raise Exception(fileName + methodName + "Error: a file exists at " + infopath + ". Use overwrite = True to overwrite.")
		return
	if (overwrite) and os.path.isfile(infopath):
		os.remove(infopath)
	f_handle = open(infopath,'a')
	for key in infokeys:
		if key in ['antloc', 'ubl', 'degenM', 'AtAi','BtBi','AtAiAt','BtBiBt','PA','PB','ImPA','ImPB']:
			np.savetxt(f_handle, [np.array(info[key]).flatten()])
		elif key == 'ublindex':
			np.savetxt(f_handle, [np.concatenate(info[key]).flatten()], fmt = '%d')
		elif key in ['At','Bt']:
			tmp = []
			for i in range(info[key].shape[0]):
				for j in range(info[key].shape[1]):
					if info[key][i,j] != 0:
						tmp += [i, j, info[key][i,j]]
			np.savetxt(f_handle, [np.array(tmp).flatten()], fmt = '%d')
		elif key in ['A','B']:
			np.savetxt(f_handle, info[key].todense().flatten(), fmt = '%d')
		else:
			np.savetxt(f_handle, [np.array(info[key]).flatten()], fmt = '%d')
	f_handle.close()
	return

def importuvs(uvfilenames, info, wantpols):
	METHODNAME = "*importuvs*"
	latP = -0.53619181096511903#todo: figure this out from uv files
	lonP = 0.37399448506783717
	############################################################
	sa = ephem.Observer()
	sa.lon = lonP #//todo: read from uv property
	sa.lat = latP
	sun = ephem.Sun()
	julDelta = 2415020 # =julian date - pyephem's Observer date
	####get some info from the first uvfile
	uv=ap.miriad.UV(uvfilenames[0])
	nfreq = uv.nchan;
	nant = uv['nants'] / 2 # 'nants' counting ant-pols, so divide 2
	startfreq = uv['sfreq']
	dfreq = uv['sdf']
	del(uv)
	####prepare processing
	deftime = 2000
	data = np.zeros((deftime, len(wantpols), nant * (nant + 1) / 2, nfreq), dtype = 'complex64')
	#sunpos = np.zeros((deftime, 2))
	t = []
	timing = []
	lst = []

	###start processing
	datapulled = False
	for uvfile in uvfilenames:
		uv = ap.miriad.UV(uvfile)
		if len(timing) > 0:
			print FILENAME + METHODNAME + "MSG:",  timing[-1]#uv.nchan
		#print FILENAME + " MSG:",  uv['nants']
		currentpol = 0
		for preamble, rawd in uv.all():
			if len(t) < 1 or t[-1] != preamble[1]:#first bl of a timeslice
				t += [preamble[1]]
				sa.date = preamble[1] - julDelta
				#sun.compute(sa)
				timing += [sa.date.__str__()]
				lst += [(float(sa.sidereal_time()) * 24./2./math.pi)]
				if len(t) > len(data):
					print FILENAME + METHODNAME + " MSG:",  "expanding number of time slices from", len(data), "to", len(data) + deftime
					data = np.concatenate((data, np.zeros((deftime, len(wantpols), nant * (nant + 1) / 2, nfreq), dtype = 'complex64')))
					#sunpos = np.concatenate((sunpos, np.zeros((deftime, 2))))
					#sunpos[len(t) - 1] = np.asarray([[sun.alt, sun.az]])
			for p, pol in zip(range(len(wantpols)), wantpols.keys()):
				if wantpols[pol] == uv['pol']:#//todo: use select()
					a1, a2 = preamble[2]
					bl = info[p]['bl1dmatrix'][a1, a2]
					if bl < info[p]['nBaseline']:
						datapulled = True
						#print info[p]['subsetbl'][info[p]['crossindex'][bl]],
						data[len(t) - 1, p, info[p]['subsetbl'][info[p]['crossindex'][bl]]] = rawd.data.astype('complex64')
		del(uv)
		if not datapulled:
			print FILENAME + METHODNAME + " MSG:",  "FATAL ERROR: no data pulled from " + uvfile + ", check polarization information! Exiting."
			exit(1)
	return data[:len(t)], t, timing, lst


def apply_omnical_uvs(uvfilenames, calparfilenames, info, wantpols, oppath, ano):
	METHODNAME = "*apply_omnical_uvs*"

	####get some info from the first uvfile
	uv=ap.miriad.UV(uvfilenames[0])
	nfreq = uv.nchan;
	nant = uv['nants'] / 2 # 'nants' counting ant-pols, so divide 2
	startfreq = uv['sfreq']
	dfreq = uv['sdf']
	del(uv)

	####load calpar and check dimensions, massage calpar from txfx(3+2a+2u) to t*goodabl*f
	blcalpar = []#calpar for each baseline, auto included
	for p in range(len(wantpols)):
		calpar = np.fromfile(calparfilenames[p], dtype='float32')
		if len(calpar)%(nfreq *( 3 + 2 * (info[p]['nAntenna'] + info[p]['nUBL']))) != 0:
			print FILENAME + METHODNAME + " MSG:",  "FATAL ERROR: calpar input array " + calparfilenames[p] + " has length", calpar.shape, "which is not divisible by ", nfreq, 3 + 2 * (info[p]['nAntenna'] + info[p]['nUBL']), "Aborted!"
			return
		ttotal = len(calpar)/(nfreq *( 3 + 2 * (info[p]['nAntenna'] + info[p]['nUBL'])))
		calpar = calpar.reshape((ttotal, nfreq, ( 3 + 2 * (info[p]['nAntenna'] + info[p]['nUBL']))))
		calpar = (10**calpar[:,:,3:3+info[p]['nAntenna']])*np.exp(1.j * calpar[:,:,3+info[p]['nAntenna']:3+2*info[p]['nAntenna']] * math.pi / 180)
		blcalpar.append(1 + np.zeros((ttotal, info[p]['nBaseline'], nfreq),dtype='complex64'))
		for bl in range(info[p]['nBaseline']):
			blcalpar[p][:, bl, :] *= (calpar[:, :, info[p]['bl2d'][bl,0]].conj() * calpar[:, :, info[p]['bl2d'][bl, 1]])



	#########start processing#######################
	t = []
	timing = []
	#datapulled = False
	for uvfile in uvfilenames:
		uvi = ap.miriad.UV(uvfile)
		if len(timing) > 0:
			print FILENAME + METHODNAME + "MSG:", uvfile + ' after', timing[-1]#uv.nchan
		uvo = ap.miriad.UV(oppath + os.path.basename(os.path.dirname(uvfile+'/')) + ano + 'omnical', status='new')
		uvo.init_from_uv(uvi)
		historystr = "Applied "
		for cpfn in calparfilenames:
			historystr += cpfn
#		uvo.pipe(uvi, mfunc=applycp, append2hist=historystr + "\n")
		for preamble, data, flag in uvi.all(raw=True):
			uvo.copyvr(uvi)
			if len(t) < 1 or t[-1] != preamble[1]:#first bl of a timeslice
				t += [preamble[1]]

				if len(t) > ttotal:
					print FILENAME + METHODNAME + " MSG: FATAL ERROR: calpar input array " + calparfilenames[p] + " has length", calpar.shape, "but the total length is exceeded when processing " + uvfile + " Aborted!"
					return
			for p, pol in zip(range(len(wantpols)), wantpols.keys()):
				if wantpols[pol] == uvi['pol']:
					a1, a2 = preamble[2]
					bl = info[p]['bl1dmatrix'][a1, a2]
					if bl < info[p]['ncross']:
						#datapulled = True
						#print info[p]['subsetbl'][info[p]['crossindex'][bl]],
						uvo.write(preamble, data/blcalpar[p][len(t) - 1, info[p]['crossindex'][bl]], flag)
					#//todo: correct autocorr as well
					else:
						uvo.write(preamble, data, flag)

		del(uvo)
		del(uvi)
		#if not datapulled:
			#print FILENAME + METHODNAME + " MSG:",  "FATAL ERROR: no data pulled from " + uvfile + ", check polarization information! Exiting."
			#exit(1)
	return


def stdmatrix(length, polydegree):#to find out the error in fitting y by a polynomial poly(x), one compute error vector by (I-A.(At.A)^-1 At).y, where Aij = i^j. This function returns (I-A.(At.A)^-1 At)
	A = np.array([[i**j for j in range(polydegree + 1)] for i in range(length)], dtype='int')
	At = A.transpose()
	return np.identity(length) - A.dot(la.pinv(At.dot(A)).dot(At))

#compare if two redundant info are the same
def compare_info(info1,info2):
	try:
		infokeys = ['nAntenna','nUBL','nBaseline','subsetant','antloc','subsetbl','ubl','bltoubl','reversed','reversedauto','autoindex','crossindex','bl2d','ublcount','bl1dmatrix','AtAi','BtBi','AtAiAt','BtBiBt','PA','PB','ImPA','ImPB']
		infomatrices=['A','B','At','Bt']
		diff=[]
		#10**5 for floating point errors
		for key in infokeys:	
			diff.append(round(10**5*la.norm(info1[key]-info2[key])))
		for key in infomatrices:
			diff.append(round(10**5*la.norm((info1[key]-info2[key]).todense())))
		for i in info1['ublindex']-info2['ublindex']:
			diff.append(round(10**5*la.norm(i)))
		bool = True
		for i in diff:
			bool = bool and i==0
		return bool
	except ValueError:
		print "info doesn't have the same shape"
		return False


class RedundantCalibrator:

	def __init__(self, nTotalAnt, info = None):
		methodName = '.__init__.'
		self.className = '.RedundantCalibrator.'
		self.nTotalAnt = nTotalAnt
		self.nTotalBaselineAuto = (self.nTotalAnt + 1) * self.nTotalAnt / 2
		self.nTotalBaselineCross = (self.nTotalAnt - 1) * self.nTotalAnt / 2
		self.antennaLocation = np.zeros((self.nTotalAnt, 3))
		self.antennaLocationTolerance = 10**(-6)
		self.badAntenna = []
		self.badUBL = []
		self.totalVisibilityId = np.concatenate([[[i,j] for i in range(j + 1)] for j in range(self.nTotalAnt)])#PAPER miriad convention by default
		self.info = None
		self.infoFileExist = False
		self.infoPath = None
		self.dataFileExist = False
		self.keepData = False
		self.tmpDataPath = './tmp_calibration_omni_data'
		self.dataPath = self.tmpDataPath #complex128 type binary visibility file
		self.keepCalpar = False
		self.calparPath = None
		self.nFrequency = -1
		self.nTime = -1
		self.removeDegeneracy = True
		self.removeAdditive = False
		self.removeAdditivePeriod = -1
		self.convergePercent = 0.01 #convergence criterion in relative change of chi^2. By default it stops when reaches 0.01, namely 1% decrease in chi^2.
		self.maxIteration = 50 #max number of iterations in lincal
		self.stepSize = 0.3 #step size for lincal. (0, 1]. < 0.4 recommended.

		if info != None:
			if type(info) == type({}):
				self.info = info
			elif type(info) == type('a'):
				self.info = read_redundantinfo(info)
				self.infoPath = info
				self.infoFileExist = True
			else:
				raise Exception(self.className + methodName + "Error: info argument not recognized. It must be of either dictionary type (an info dictionary) *OR* string type (path to the info file).")

	def read_redundantinfo(self, infopath):
		self.infoPath = infopath
		self.info = read_redundantinfo(infopath)
		self.infoFileExist = True

	def write_redundantinfo(self, infoPath = None):
		methodName = '.write_redundantinfo.'
		if infoPath == None:
			infoPath = self.infoPath
		if (self.info != None) and (self.infoFileExist == False) and (infoPath != None):
			write_redundantinfo(self.info, infoPath)
			self.infoFileExist = True
		else:
			raise Exception(self.className + methodName + "Error: either 1) info does not yet exist for the current instance, or 2) an info file already exists on disk, or 3) no file path is ever specified.")


	def readyForCpp(self, verbose = True):#todo check if all parameters are specified to call Cpp
		methodName = '.readyForCpp.'
		if os.path.getsize(self.dataPath) / 8 != self.nTime * self.nFrequency * self.nTotalBaselineAuto:
			if verbose:
				print self.className + methodName + "Error: data size check failed. File on disk seems to contain " + str(os.path.getsize(self.dataPath) / 8) + " complex64 numbers, where as we expect " + str(self.nTime * self.nFrequency * self.nTotalBaselineAuto) + '.'
			return False

		if not self.infoFileExist :
			if verbose:
				print self.className + methodName + "Error: info file existence check failed. Call read_redundantinfo(self, infoPath) function to read in an existing redundant info text file or write_redundantinfo(self, infoPath) to write a new text file."
			return False

		if self.removeAdditive and self.removeAdditivePeriod <= 0:
			if verbose:
				print self.className + methodName + "Error: removeAdditive option is True but the removeAdditivePeriod parameter is negative (invalid)."
			return False

		if abs(self.convergePercent - 0.5) >= 0.5 or self.maxIteration <= 0 or abs(self.stepSize - 0.5) >= 0.5:
			if verbose:
				print self.className + methodName + "Error: lincal parameter check failed. convergePercent and stepSize should be between 0 and 1, and maxIteration has to be positive integer."
			return False
		if verbose:
			print self.className + methodName + "Check passed."
		return True

	def cal(self, data, verbose = False):#data can be either 3d numpy array or a binary file path
		methodName = '.cal.'
		if type(data) == type(' '):
			self.dataPath = data
		elif type(data) == type(np.zeros(1)) and len(data.shape) == 3 and len(data[0,0]) == self.nTotalBaselineAuto and self.dataPath == self.tmpDataPath:
			(self.nTime, self.nFrequency, _) = data.shape
			np.array(data, dtype = 'complex64').tofile(self.tmpDataPath)
			self.dataPath = self.tmpDataPath
		else:
			raise Exception(self.className + methodName + "Error: data type must be a file path name to a binary file *OR* a 3D numpy array of dimensions (nTime, nFrequency, nTotalBaselineAuto). You have either 1) passed in the wrong type, or 2) passed in a correct data array but have mismatching self.dataPath and self.tmpDataPath (these paths will be overwritten if you pass in an array as data!).")

		if self.readyForCpp(verbose = False):
			command = "./omnical " + self.dataPath + " " + self.infoPath + " " + str(self.nTime) + " " + str(self.nFrequency) + " "  + str(self.nTotalAnt) + " " + str(int(self.removeDegeneracy)) + " " + str(int(self.removeAdditive)) + " " + str(self.removeAdditivePeriod) + " " + self.calMode + " " + str(self.convergePercent) + " " + str(self.maxIteration) + " " + str(self.stepSize)
			if verbose:
				print self.className + methodName + "System call: " + command
			os.system(command)

			self.calparPath = self.dataPath + '.omnical'
			self.rawCalpar = np.fromfile(self.calparPath, dtype = 'float32').reshape((self.nTime, self.nFrequency, 3 + 2 * (self.info['nAntenna'] + self.info['nUBL'])))
			if self.calMode == '0' or self.calMode == '1':
				self.chisq = self.rawCalpar[:, :, 2]
			elif self.calMode == '2':
				self.chisq = self.rawCalpar[:, :, 1]
			self.calpar = (10**(self.rawCalpar[:, :, 3: (3 + self.info['nAntenna'])])) * np.exp(1.j * np.pi * self.rawCalpar[:, :, (3 + self.info['nAntenna']): (3 + 2 * self.info['nAntenna'])] / 180)
			self.bestfit = self.rawCalpar[:, :, (3 + 2 * self.info['nAntenna']):: 2] + 1.j * self.rawCalpar[:, :, (4 + 2 * self.info['nAntenna']):: 2]
			if not self.keepCalpar:
				os.remove(self.calparPath)
			if not self.keepData and self.dataPath == self.tmpDataPath:
				os.remove(self.dataPath)
		else:
			raise Exception(self.className + methodName + "Error: function is called prematurely. The current instance failed the readyForCpp() check. Try instance.readyForCpp() for more info.")


	def loglincal(self, data, verbose = False):
		self.calMode = '1'
		self.cal(data, verbose)

	def lincal(self, data, verbose = False):
		self.calMode = '0'
		self.cal(data, verbose)

	def logcal(self, data, verbose = False):#todo
		raise Exception(self.className + "Error: logcal function is not yet implemented.")
		#self.calMode = '2'
		#self.cal(data, verbose)

	def compute_info(self, configFilePath = None):#todo
		#nAntenna and subsetant : get rid of the bad antennas
		nant=len(self.antennaLocation)
		subsetant=[i for i in range(nant) if i not in self.badAntenna]
		nAntenna=len(subsetant)
		antloc=[self.antennaLocation[ant] for ant in subsetant]
		##########################################################################################
		#find out ubl
		#antloc has the form of a nested list with dimension nant*3, returns a np array of unique baselines
		def UBL(antloc,tolerance):
			ubllist=np.array([np.array([0,0,0])]);
			for i in range(len(antloc)):
				for j in range(i+1,len(antloc)):
					bool = False;
					for bl in ubllist:
						bool = bool or (np.linalg.norm(antloc[i]-antloc[j]-bl)<tolerance or np.linalg.norm(antloc[i]-antloc[j]+bl)<tolerance)
					if bool == False:			
						ubllist = np.concatenate((ubllist,[antloc[j]-antloc[i]]))
			ublall=np.delete(ubllist,0,0)
			return ublall
		#use the function above to find the ubl
		tolerance=self.antennaLocationTolerance;		
		ublall=UBL(antloc,tolerance)
		#delete the bad ubl's
		ubl=np.delete(ublall,np.array(self.badUBL),0)
		nUBL=len(ubl);
		#################################################################################################
		#calculate the norm of the difference of two vectors (just la.norm actually)
		def dis(a1,a2):
			return np.linalg.norm(np.array(a1)-np.array(a2))
		#find nBaseline (include auto baselines) and subsetbl
		badbl=[ublall[i] for i in self.badUBL]
		nbl=0;
		goodpairs=[];
		for i in range(len(antloc)):
			for j in range(i+1):
				bool=False
				for bl in badbl:
					bool = bool or dis(antloc[i]-antloc[j],bl)<tolerance or dis(antloc[i]-antloc[j],-bl)<tolerance
				if bool == False:
					nbl+=1
					goodpairs.append([i,j])
		nBaseline=len(goodpairs)
		#from antenna pair to baseline index
		def toBaseline(pair,tvid=self.totalVisibilityId):
			sortp=np.array(sorted(pair))
			for i in range(len(tvid)):
				if tvid[i][0] == subsetant[sortp[0]] and tvid[i][1] == subsetant[sortp[1]]:
					return i
			return 'no match'
		subsetbl=np.array([toBaseline(bl,self.totalVisibilityId) for bl in goodpairs])			
		##################################################################################
		#bltoubl: cross bl number to ubl index
		def findublindex(pair,ubl=ubl):
			i=pair[0]
			j=pair[1]
			for k in range(len(ubl)):
				if dis(antloc[i]-antloc[j],ubl[k])<tolerance or dis(antloc[i]-antloc[j],-ubl[k])<tolerance:
					return k
			return "no match"
		bltoubl=[];
		for i in goodpairs:
			if i[0]!=i[1]:
				bltoubl.append(findublindex(i)) 	
		#################################################################################
		#reversed:   cross only bl if reversed -1, otherwise 1
		crosspair=[]
		for p in goodpairs:
			if p[0]!=p[1]:
				crosspair.append(p)
		reverse=[]
		for k in range(len(crosspair)):
			i=crosspair[k][0]
			j=crosspair[k][1]
			if dis(antloc[i]-antloc[j],ubl[bltoubl[k]])<tolerance:
				reverse.append(1)
			elif dis(antloc[i]-antloc[j],-ubl[bltoubl[k]])<tolerance:
				reverse.append(-1)
			else :
				print "something's wrong with bltoubl"
		######################################################################################
		#reversedauto: the index of good baselines (auto included) in all baselines
		#autoindex: index of auto bls among good bls
		#crossindex: index of cross bls among good bls
		#ncross
		reversedauto = range(len(goodpairs))
		#find the autoindex and crossindex in goodpairs
		autoindex=[]
		crossindex=[]
		for i in range(len(goodpairs)):
			if goodpairs[i][0]==goodpairs[i][1]:
				autoindex.append(i)
			else:
				crossindex.append(i)
		for i in autoindex:
			reversedauto[i]=1
		for i in range(len(crossindex)):
			reversedauto[crossindex[i]]=reverse[i]
		reversedauto=np.array(reversedauto)
		autoindex=np.array(autoindex)
		crossindex=np.array(crossindex)
		ncross=len(crossindex)
		###################################################
		#bl2d:  from 1d bl index to a pair of antenna numbers
		bl2d=[]
		for pair in goodpairs:
			bl2d.append(pair[::-1])
		bl2d=np.array(bl2d)
		###################################################
		#ublcount:  for each ubl, the number of good cross bls corresponding to it
		countdict={}
		for bl in bltoubl:
			countdict[bl]=0
			
		for bl in bltoubl:
			countdict[bl]+=1
			
		ublcount=[]
		for i in range(nUBL):
			ublcount.append(countdict[i])
		ublcount=np.array(ublcount)
		####################################################################################
		#ublindex:  //for each ubl, the vector<int> contains (ant1, ant2, crossbl)
		countdict={}
		for bl in bltoubl:
			countdict[bl]=[]
			
		for i in range(len(crosspair)):
			ant1=crosspair[i][1]
			ant2=crosspair[i][0]
			countdict[bltoubl[i]].append([ant1,ant2,i])
			
		ublindex=[]
		for i in range(nUBL):
			ublindex.append(countdict[i])
		#turn each list in ublindex into np array	
		for i in range(len(ublindex)):
			ublindex[i]=np.array(ublindex[i])
		ublindex=np.array(ublindex)
		###############################################################################
		#bl1dmatrix: a symmetric matrix where col/row numbers are antenna indices and entries are 1d baseline index not counting auto corr
				#I suppose 99999 for bad and auto baselines?
		bl1dmatrix=99999*np.ones([nAntenna,nAntenna],dtype='int16')
		for i in range(len(crosspair)):
			bl1dmatrix[crosspair[i][1]][crosspair[i][0]]=i
			bl1dmatrix[crosspair[i][0]][crosspair[i][1]]=i
		####################################################################################3
		#degenM:
		a=[] 
		for i in range(len(antloc)):
			a.append(np.append(antloc[i],1))
		a=np.array(a)
		
		d=[]
		for i in range(len(ubl)):
			d.append(np.append(ubl[i],0))
		d=np.array(d)
		
		m1=-a.dot(la.pinv(np.transpose(a).dot(a))).dot(np.transpose(a))
		m2=d.dot(la.pinv(np.transpose(a).dot(a))).dot(np.transpose(a))
		degenM = np.append(m1,m2,axis=0)
		#####################################################################################
		#A: A matrix for logcal amplitude
		A=np.zeros([len(crosspair),nAntenna+len(ubl)])
		for i in range(len(crosspair)):
			A[i][crosspair[i][0]]=1
			A[i][crosspair[i][1]]=1
			A[i][nAntenna+bltoubl[i]]=1
		A=sps.csr_matrix(A)
		#################################################################################
		#B: B matrix for logcal phase
		B=np.zeros([len(crosspair),nAntenna+len(ubl)])
		for i in range(len(crosspair)):
			B[i][crosspair[i][0]]=reverse[i]*1
			B[i][crosspair[i][1]]=reverse[i]*-1
			B[i][nAntenna+bltoubl[i]]=1
		B=sps.csr_matrix(B)
		###########################################################################
		#create info dictionary
		info={}
		info['nAntenna']=nAntenna
		info['nUBL']=nUBL
		info['nBaseline']=nBaseline
		info['subsetant']=subsetant
		info['antloc']=antloc
		info['subsetbl']=subsetbl
		info['ubl']=ubl
		info['bltoubl']=bltoubl
		info['reversed']=reverse
		info['reversedauto']=reversedauto
		info['autoindex']=autoindex
		info['crossindex']=crossindex
		info['ncross']=ncross
		info['bl2d']=bl2d
		info['ublcount']=ublcount
		info['ublindex']=ublindex
		info['bl1dmatrix']=bl1dmatrix
		info['degenM']=degenM
		info['A']=A
		info['B']=B
		with warnings.catch_warnings():
				warnings.filterwarnings("ignore",category=DeprecationWarning)
				info['At'] = info['A'].transpose()
				info['Bt'] = info['B'].transpose()
				info['AtAi'] = la.pinv(info['At'].dot(info['A']).todense())#(AtA)^-1
				info['BtBi'] = la.pinv(info['Bt'].dot(info['B']).todense())#(BtB)^-1
				info['AtAiAt'] = info['AtAi'].dot(info['At'].todense())#(AtA)^-1At
				info['BtBiBt'] = info['BtBi'].dot(info['Bt'].todense())#(BtB)^-1Bt
				info['PA'] = info['A'].dot(info['AtAiAt'])#A(AtA)^-1At
				info['PB'] = info['B'].dot(info['BtBiBt'])#B(BtB)^-1Bt
				info['ImPA'] = sps.identity(ncross) - info['PA']#I-PA
				info['ImPB'] = sps.identity(ncross) - info['PB']#I-PB
		self.info=info


	#inverse function of totalVisibilityId, calculate the baseline index from the antenna pair
	def get_baseline(self,pair): 
		if not (type(pair) == list or type(pair) == np.ndarray or type(pair) == tuple):
			raise Exception("input needs to be a list of two numbers")
			return 
		elif len(np.array(pair)) != 2:
			raise Exception("input needs to be a list of two numbers")
			return 
		elif type(pair[0]) == str or type(pair[0]) == np.string_:
			raise Exception("input needs to be number not string")
			return
		sortp = np.array(sorted(pair))
		for i in range(len(self.totalVisibilityId)):
			if self.totalVisibilityId[i][0] == sortp[0] and self.totalVisibilityId[i][1] == sortp[1]:
				return i
		raise Exception("antenna index out of range")

	#with antenna locations and tolerance, calculate the unique baselines. (In the order of omniscope baseline index convention)
	def compute_UBL(self,tolerance = 0.1):
		#check if the tolerance is not a string
		if type(tolerance) == str:
			raise Exception("tolerance needs to be number not string")
			return
			
		antloc=self.antennaLocation
		ubllist=np.array([np.array([0,0,0])]);
		for i in range(len(antloc)):
			for j in range(i+1,len(antloc)):
				bool = False;
				for bl in ubllist:
					bool = bool or (la.norm(antloc[i]-antloc[j]-bl)<tolerance or la.norm(antloc[i]-antloc[j]+bl)<tolerance)
				if bool == False:			
					ubllist = np.concatenate((ubllist,[antloc[j]-antloc[i]]))
		ublall = np.delete(ubllist,0,0)
		return ublall
		

	#need to do compute_info first for this function to work
	#input the antenna pair(as a list of two numbers), return the corresponding ubl index
	def get_ublindex(self,antpair):
		#check if the input is a list, tuple, np.array of two numbers
		if not (type(antpair) == list or type(antpair) == np.ndarray or type(antpair) == tuple):
			raise Exception("input needs to be a list of two numbers")
			return 
		elif len(np.array(antpair)) != 2:
			raise Exception("input needs to be a list of two numbers")
			return 
		elif type(antpair[0]) == str or type(antpair[0]) == np.string_:
			raise Exception("input needs to be number not string")
			return
			
		crossblindex=self.info['bl1dmatrix'][antpair[0]][antpair[1]]
		if antpair[0]==antpair[1]:
			return "auto correlation"
		elif crossblindex == 99999:
			return "bad ubl"
		return self.info['bltoubl'][crossblindex]
		

	#need to do compute_info first
	#input the antenna pair, return -1 if it is a reversed baseline and 1 if it is not reversed
	def get_reversed(self,antpair):
		#check if the input is a list, tuple, np.array of two numbers
		if not (type(antpair) == list or type(antpair) == np.ndarray or type(antpair) == tuple):
			raise Exception("input needs to be a list of two numbers")
			return 
		elif len(np.array(antpair)) != 2:
			raise Exception("input needs to be a list of two numbers")
			return 
		elif type(antpair[0]) == str or type(antpair[0]) == np.string_:
			raise Exception("input needs to be number not string")
			return
		
		crossblindex=self.info['bl1dmatrix'][antpair[0]][antpair[1]]
		if antpair[0] == antpair[1]:
			return 1
		if crossblindex == 99999:
			return 'badbaseline'
		return self.info['reversed'][crossblindex]
		
		
		
		
		


