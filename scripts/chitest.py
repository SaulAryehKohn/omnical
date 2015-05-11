#!/usr/bin/env python

import numpy as np
import commands, os, time, math, ephem
import omnical.calibration_omni as omni
import optparse, sys
FILENAME = "chitest.py"


sides = [4]#[3,4,5]#,12,16,20,24]
noises = [0.0] + (10.**np.arange(-5, 1, .4)).tolist()
times = np.zeros((len(sides), len(noises), 6))
trust_period = 1
step_size = .3
use_log = False
nt = 1000
nf = 100

thetas = [.1, .4, .7, .8, 1.3, 1.4]
phis = [.2, .8, 1.9, 2.8, 3.5, 4.5, 5]


for phase_noise in [0, .01, .1, .3]:#0, .01, .1, 

    opname = "step%f_ps%i_g%f_log%i_chi2.txt"%(step_size, len(thetas) * len(phis), phase_noise, use_log)

    for nside, side in enumerate(sides):
        nant = side**2
        print "Starting %i antennas"%nant
        calibrator = omni.RedundantCalibrator(nant)

        print "Reading readundant info"
        calibrator.read_redundantinfo(os.path.dirname(os.path.realpath(__file__)) + '/../results/%i.bin'%nant, verbose = False)
        calibrator.removeDegeneracy = False
        calibrator.removeAdditive = False
        calibrator.keepData = False
        calibrator.keepCalpar = False
        calibrator.convergePercent = 1e-6
        calibrator.maxIteration = 2000
        calibrator.stepSize = step_size
        calibrator.computeUBLFit = True
        calibrator.nTime = nt
        calibrator.nFrequency = nf
        calibrator.trust_period = trust_period
        
        DoF = len(calibrator.Info.crossindex) - (calibrator.Info.nUBL + calibrator.Info.nAntenna)# - 2)

        data = np.zeros((nt, nf, max(calibrator.Info.subsetbl) + 1), dtype='complex64')

        g_amp = np.random.randn(nant) * phase_noise
        gg_amp = g_amp[calibrator.Info.bl2d[calibrator.Info.crossindex, 0]] + g_amp[calibrator.Info.bl2d[calibrator.Info.crossindex, 1]]
        g_phase = np.random.randn(nant) * phase_noise
        gg_phase = -g_phase[calibrator.Info.bl2d[calibrator.Info.crossindex, 0]] + g_phase[calibrator.Info.bl2d[calibrator.Info.crossindex, 1]]
        for th1 in thetas:
            for ph1 in phis:
                k1 = np.array([np.sin(th1) * np.cos(ph1), np.sin(th1) * np.sin(ph1), np.cos(th1)])
                vis_phase = (2*np.pi*calibrator.Info.ubl.dot(k1))[calibrator.Info.bltoubl] * calibrator.Info.reversed

                data[:, :, calibrator.Info.subsetbl[calibrator.Info.crossindex]] += np.cos(th1) **2 * np.exp(1.j * vis_phase)[None,None,:] 
        data = data / np.mean(np.abs(data))
        model = np.copy(data[0,0])

        gdata = np.copy(data)
        gdata[:, :, calibrator.Info.subsetbl[calibrator.Info.crossindex]] *= np.exp(gg_amp + 1.j * gg_phase)[None,None,:]
        gdata = gdata / np.mean(np.abs(gdata))
        

        timer = omni.Timer()
        for nnoise, noise in enumerate(noises):
            nn = (noise / 1.41421 * (np.random.randn(*gdata.shape) + np.random.randn(*gdata.shape) * 1.j)).astype('complex64')
            ndata = gdata + nn
            real_data = np.copy(ndata[0,0])
            #print ndata.shape, ndata.dtype
            timer.tick(noise, mute = True)
            if use_log:
                calibrator.logcal(ndata, np.zeros_like(ndata), verbose=True)
            calibrator.lincal(ndata, np.zeros_like(ndata), verbose=True)
            times[nside, nnoise, 0], _ = timer.tick(noise)
            times[nside, nnoise, 1] = np.average(calibrator.rawCalpar[:, :, 2])
            times[nside, nnoise, 2] = (2*DoF)**.5 / (nt * nf)**.5
            if noise != 0:
                times[nside, nnoise, 3] = np.average(calibrator.rawCalpar[:, :, 2])/noise**2.
                times[nside, nnoise, 5] = np.average(calibrator.rawCalpar[:, :, 2])/noise**2./DoF
            else:
                times[nside, nnoise, 3] = np.average(calibrator.rawCalpar[:, :, 2])
                times[nside, nnoise, 5] = np.average(calibrator.rawCalpar[:, :, 2])/DoF
            times[nside, nnoise, 4] = DoF
            cal_data = calibrator.get_calibrated_data(ndata)[0,0]
            #omni.omniview(np.array([model, real_data, cal_data]), calibrator.Info)

            
            #####sanity check: if input perfect calibration parameter, chi^2 should be ~1
            ####ndata = data + nn
            #####print ndata.shape, ndata.dtype
            ####timer.tick(noise, mute = True)
            ####calibrator.computeUBLFit = True
            ####calibrator.logcal(ndata, np.zeros_like(ndata), verbose=True)
            ####calibrator.lincal(ndata, np.zeros_like(ndata), verbose=True)
            ####if noise != 0:
                ####times[nside, nnoise, 4] = np.average(calibrator.rawCalpar[:, :, 2])/noise**2./DoF
            ####else:
                ####times[nside, nnoise, 4] = np.average(calibrator.rawCalpar[:, :, 2])/DoF
                

    oppath = os.path.dirname(os.path.realpath(__file__)) + '/../results/' + opname 
    while os.path.isfile(oppath):
        oppath += '_'
    np.savetxt(oppath, times.reshape((len(times) * len(times[0]), len(times[0,0]))), fmt='%.4E')
