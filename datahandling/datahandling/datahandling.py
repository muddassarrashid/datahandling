import datahandling.LeCroy
import matplotlib.pyplot as _plt
import numpy as _np
import scipy.signal
from bisect import bisect_left as _bisect_left
from scipy.optimize import curve_fit as _curve_fit
import uncertainties as _uncertainties
from mpl_toolkits.mplot3d.axes3d import Axes3D
from matplotlib import rcParams
import matplotlib.animation as _animation
from glob import glob
import re
import seaborn as _sns
import pandas as _pd
import fnmatch as _fnmatch
from multiprocessing import Pool as _Pool
from multiprocessing import cpu_count as _cpu_count
from scipy.optimize import minimize as _minimize
import warnings as _warnings
from scipy.signal import hilbert as _hilbert


class DataObject():
    """
    Creates an object containing data and all it's properties.

    Attributes
    ----------
    filepath : string
            filepath to the file containing the data used to initialise
            this particular instance of the DataObject class
    filename : string
            filename of the file containing the data used to initialise
            this particular instance of the DataObject class
    waveDescription : dictionary
            Contains various information about the data as it was collected.
    time : ndarray
            Contains the time data in seconds
    voltage : ndarray
            Contains the voltage data in Volts
    SampleFreq : sample frequency used to sample the data (when it was
            taken by the oscilloscope)
    freqs : ndarray
            Contains the frequencies corresponding to the PSD (Pulse Spectral
            Density)
    PSD : ndarray
            Contains the values for the PSD (Pulse Spectral Density) as calculated
            at each frequency contained in freqs

    """

    def __init__(self, filepath):
        """
        Parameters
        ----------
        filepath : string
            The filepath to the data file to initialise this object instance.

        Initialisation - assigns values to the following attributes:
        - filepath
        - filename
        - filedir
        - time
        - voltage
        - freqs
        - PSD
        """
        self.filepath = filepath
        self.filename = filepath.split("/")[-1]
        self.filedir = self.filepath[0:-len(self.filename)]
        self.get_time_data()
        self.get_PSD()
        return None

    def get_time_data(self):
        """
        Gets the time and voltage data and the wave description.

        Returns
        -------
        time : ndarray
                        array containing the value of time (in seconds) at which the
                        voltage is sampled
        voltage : ndarray
                        array containing the sampled voltages
        """
        f = open(self.filepath, 'rb')
        raw = f.read()
        f.close()
        self.waveDescription, self.time, self.voltage, _ = \
            datahandling.LeCroy.InterpretWaveform(raw)
        self.SampleFreq = (1 / self.waveDescription["HORIZ_INTERVAL"])
        return self.time, self.voltage

    def plot_time_data(self, timeStart="Default", timeEnd="Default", ShowFig=True):
        """
        plot time data against voltage data.

        Parameters
        ----------
        timeStart : float, optional
            The time to start plotting from.
            By default it uses the first time point
        timeEnd : float, optional
            The time to finish plotting at.
            By default it uses the last time point
        ShowFig : bool, optional
            If True runs plt.show() before returning figure
            if False it just returns the figure object.
            (the default is True, it shows the figure)

        Returns
        -------
        fig : plt.figure
            The figure object created
        ax : fig.add_subplot(111)
            The subplot object created
        """
        if timeStart == "Default":
            timeStart = self.time[0]
        if timeEnd == "Default":
            timeEnd = self.time[-1]

        StartIndex = list(self.time).index(take_closest(self.time, timeStart))
        EndIndex = list(self.time).index(take_closest(self.time, timeEnd))

        fig = _plt.figure(figsize=[10, 6])
        ax = fig.add_subplot(111)
        ax.plot(self.time[StartIndex:EndIndex],
                self.voltage[StartIndex:EndIndex])
        ax.set_xlabel("time (s)")
        ax.set_ylabel("voltage (V)")
        ax.set_xlim([timeStart, timeEnd])
        if ShowFig == True:
            _plt.show()
        return fig, ax

    def get_PSD(self, NPerSegment='Default', window="hann"):
        """
        Extracts the pulse spectral density (PSD) from the data.

        Parameters
        ----------
        NPerSegment : int, optional
            Length of each segment used in scipy.welch
            default = the Number of time points

        window : str or tuple or array_like, optional
            Desired window to use. See get_window for a list of windows
            and required parameters. If window is array_like it will be
            used directly as the window and its length will be used for
            nperseg.
            default = "hann"

        Returns
        -------
        freqs : ndarray
                Array containing the frequencies at which the PSD has been
                calculated
        PSD : ndarray
                Array containing the value of the PSD at the corresponding
                frequency value in V**2/Hz
        """
        if NPerSegment == "Default":
            NPerSegment = len(self.time)
            if NPerSegment > 1e5:
                NPerSegment = int(1e5)
        freqs, PSD = scipy.signal.welch(self.voltage, self.SampleFreq,
                                        window=window, nperseg=NPerSegment)
        PSD = PSD[freqs.argsort()]
        freqs.sort()
        self.PSD = PSD
        self.freqs = freqs
        return self.freqs, self.PSD

    def plot_PSD(self, xlim="Default", ShowFig=True):
        """
        plot the pulse spectral density.

        Parameters
        ----------
        xlim : array_like, optional
            The x limits of the plotted PSD [LowerLimit, UpperLimit]
            Default value is [0, SampleFreq/2]
        ShowFig : bool, optional
            If True runs plt.show() before returning figure
            if False it just returns the figure object.
            (the default is True, it shows the figure)

        Returns
        -------
        fig : plt.figure
                        The figure object created
                ax : fig.add_subplot(111)
                        The subplot object created
        """
#        self.get_PSD()
        if xlim == "Default":
            xlim = [0, self.SampleFreq / 2]
        fig = _plt.figure(figsize=[10, 6])
        ax = fig.add_subplot(111)
        ax.semilogy(self.freqs, self.PSD, color="blue")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_xlim(xlim)
        ax.grid(which="major")
        ax.set_ylabel("$S_{xx}$ ($v^2/Hz$)")
        if ShowFig == True:
            _plt.show()
        return fig, ax

    def calc_area_under_PSD(self, lowerFreq, upperFreq):
        """
        Sums the area under the PSD from lowerFreq to upperFreq.

        Parameters
        ----------
        lowerFreq : float
            The lower limit of frequency to sum from
        upperFreq : float
            The upper limit of frequency to sum to

        Returns
        -------
        AreaUnderPSD : float
            The area under the PSD from lowerFreq to upperFreq
        """
        Freq_startAreaPSD = take_closest(self.freqs, lowerFreq)
        index_startAreaPSD = int(_np.where(self.freqs == Freq_startAreaPSD)[0])
        Freq_endAreaPSD = take_closest(self.freqs, upperFreq)
        index_endAreaPSD = int(_np.where(self.freqs == Freq_endAreaPSD)[0])
        AreaUnderPSD = sum(self.PSD[index_startAreaPSD: index_endAreaPSD])
        return AreaUnderPSD

    def get_fit(self, TrapFreq, WidthOfPeakToFit, A_Initial=0.1e10, Gamma_Initial=400, NMovAveToFit=1, Silent=False, MakeFig=True, ShowFig=True):
        """
        Function that fits to a peak to the PSD to extract the 
        frequency, A factor and Gamma (damping) factor.

        Parameters
        ----------
        TrapFreq : float
            The approximate trapping frequency to use initially
            as the centre of the peak
        WidthOfPeakToFit : float
            The width of the peak to be fitted to. This limits the
            region that the fitting function can see in order to
            stop it from fitting to the wrong peak
        A_Initial : float, optional
            The initial value of the A parameter to use in fitting
        Gamma_Initial : float, optional
            The initial value of the Gamma parameter to use in fitting
        NMovAveToFit : int, optional
            The number of point of moving average filter to perform
            before fitting in order to smooth out the peak.
            defaults to 1.
        Silent : bool, optional
            Whether to print any output when running this function
            defaults to False
        MakeFig : bool, optional
            Whether to construct and return the figure object showing
            the fitting. defaults to True
        ShowFig : bool, optional
            Whether to show the figure object when it has been created.
            defaults to True

        Returns
        -------
        A : uncertainties.ufloat
            Fitting constant A
            A = γ**2*Γ_0*(K_b*T_0)/(π*m)
            where:
                γ = conversionFactor
                Γ_0 = Damping factor due to environment
                π = pi
        Ftrap : uncertainties.ufloat
            The trapping frequency in the z axis (in angular frequency)
        Gamma : uncertainties.ufloat
            The damping factor Gamma = Γ = Γ_0 + δΓ
            where:
                Γ_0 = Damping factor due to environment
                δΓ = extra damping due to feedback or other effects
        fig : matplotlib.figure.Figure object
            figure object containing the plot
        ax : matplotlib.axes.Axes object
            axes with the data plotted of the:
                - initial data
                - smoothed data
                - initial fit
                - final fit
        """
        if MakeFig == True:
            Params, ParamsErr, fig, ax = fit_PSD(
                self, WidthOfPeakToFit, NMovAveToFit, TrapFreq, A_Initial, Gamma_Initial, MakeFig=MakeFig, ShowFig=ShowFig)
        else:
            Params, ParamsErr, _ , _ = fit_PSD(
                self, WidthOfPeakToFit, NMovAveToFit, TrapFreq, A_Initial, Gamma_Initial, MakeFig=MakeFig, ShowFig=ShowFig)

        if Silent == False:
            print("\n")
            print("A: {} +- {}% ".format(Params[0],
                                         ParamsErr[0] / Params[0] * 100))
            print(
                "Trap Frequency: {} +- {}% ".format(Params[1], ParamsErr[1] / Params[1] * 100))
            print(
                "Big Gamma: {} +- {}% ".format(Params[2], ParamsErr[2] / Params[2] * 100))

        self.A = _uncertainties.ufloat(Params[0], ParamsErr[0])
        self.Ftrap = _uncertainties.ufloat(Params[1], ParamsErr[1])
        self.Gamma = _uncertainties.ufloat(Params[2], ParamsErr[2])

        if MakeFig == True:
            return self.A, self.Ftrap, self.Gamma, fig, ax
        else:
            return self.A, self.Ftrap, self.Gamma, None, None

    def get_fit_from_peak(self, lowerLimit, upperLimit, NumPointsSmoothing=1, Silent=False, ShowFig=True):
        """
        Finds an approximate values for the peaks central frequency, height, 
        and FWHM by looking for the heighest peak in the frequncy range defined 
        by the imput arguments. It then uses the central frequncy as the trapping 
        frequency, peak height to an approximate A value and the FWHM to an approximate
        Gamma (damping) value.

        Parameters
        ----------
        lowerLimit : float
            The lower frequency limit of the range in which it looks for a peak
        upperLimit : float
            The higher frequency limit of the range in which it looks for a peak
        NumPointsSmoothing : float
            The number of points of moving-average smoothing it applies before fitting the 
            peak.
        Silent : bool, optional
            Whether it prints the values fitted or is silent.
        ShowFig : bool, optional
            Whether it makes and shows the figure object or not.

        Returns
        -------
        Ftraps : ufloat
            Trapping frequency
        A : ufloat
            A parameter
        Gamma : ufloat
            Gamma, the damping parameter
        """
        lowerIndex = list(self.freqs).index(
            take_closest(self.freqs, lowerLimit))
        upperIndex = list(self.freqs).index(
            take_closest(self.freqs, upperLimit))

        if lowerIndex == upperIndex:
            _warnings.warn("range is too small, returning NaN", UserWarning)
            val = _uncertainties.ufloat(_np.NaN, _np.NaN)
            return val, val, val

        MaxPSD = max(self.PSD[lowerIndex:upperIndex])

        CentralFreq = self.freqs[list(self.PSD).index(MaxPSD)]
        centralIndex = list(self.freqs).index(CentralFreq)

        approx_A = MaxPSD * 1e16  # 1e16 was calibrated for a number of saves to be approximately the correct conversion factor between the height of the PSD and the A factor in the fitting

        MinPSD = min(self.PSD[lowerIndex:upperIndex])

        # need to get this on log scale
        HalfMax = MinPSD + (MaxPSD - MinPSD) / 2

        try:
            LeftSideOfPeakIndex = list(self.PSD).index(
                take_closest(self.PSD[lowerIndex:centralIndex], HalfMax))
            LeftSideOfPeak = self.freqs[LeftSideOfPeakIndex]
        except IndexError:
            _warnings.warn("range is too small, returning NaN", UserWarning)
            val = _uncertainties.ufloat(_np.NaN, _np.NaN)
            return val, val, val

        try:
            RightSideOfPeakIndex = list(self.PSD).index(
                take_closest(self.PSD[centralIndex:upperIndex], HalfMax))
            RightSideOfPeak = self.freqs[RightSideOfPeakIndex]
        except IndexError:
            _warnings.warn("range is too small, returning NaN", UserWarning)
            val = _uncertainties.ufloat(_np.NaN, _np.NaN)
            return val, val, val

        FWHM = RightSideOfPeak - LeftSideOfPeak

        approx_Gamma = FWHM/4
        try:
            self.get_fit(CentralFreq, (upperLimit-lowerLimit)/2, 
                         A_Initial=approx_A, Gamma_Initial=approx_Gamma, Silent=Silent, MakeFig=ShowFig, ShowFig=ShowFig)
        except TypeError: 
            _warnings.warn("range is too small to fit, returning NaN", UserWarning)
            val = _uncertainties.ufloat(_np.NaN, _np.NaN)
            return val, val, val
        FTrap = self.Ftrap
        A = self.A
        Gamma = self.Gamma

        omegaArray = 2 * _np.pi * \
            self.freqs[LeftSideOfPeakIndex:RightSideOfPeakIndex]
        PSDArray = self.PSD[LeftSideOfPeakIndex:RightSideOfPeakIndex]

        return FTrap, A, Gamma

    def get_fit_auto(self, CentralFreq, MaxWidth=15000, MinWidth=500, WidthIntervals=500, ShowFig=True):
        """
        Tries a range of regions to search for peaks and runs the one with the least error
        and returns the parameters with the least errors.

        Parameters
        ----------
        CentralFreq : float
            The central frequency to use for the fittings.
        MaxWidth : float, optional
            The maximum bandwidth to use for the fitting of the peaks.
        MinWidth : float, optional
            The minimum bandwidth to use for the fitting of the peaks.
        WidthIntervals : float, optional
            The intervals to use in going between the MaxWidth and MinWidth.
        ShowFig : bool, optional
            Whether to plot and show the final (best) fitting or not.

        Returns
        -------
        Ftraps : ufloat
            Trapping frequency
        A : ufloat
            A parameter
        Gamma : ufloat
            Gamma, the damping parameter
        """
        MinTotalSumSquaredError = _np.infty
        for Width in _np.arange(MaxWidth, MinWidth - WidthIntervals, -WidthIntervals):
            try:
                Ftrap, A, Gamma = self.get_fit_from_peak(
                    CentralFreq - Width / 2, CentralFreq + Width / 2, Silent=True, ShowFig=False)
            except RuntimeError:
                _warnings.warn("Couldn't find good fit with width {}".format(
                    Width), RuntimeWarning)
                val = _uncertainties.ufloat(_np.NaN, _np.NaN)
                Ftrap = val
                A = val
                Gamma = val
            TotalSumSquaredError = (
                A.std_dev / A.n)**2 + (Gamma.std_dev / Gamma.n)**2 + (Ftrap.std_dev / Ftrap.n)**2
            #print("totalError: {}".format(TotalSumSquaredError))
            if TotalSumSquaredError < MinTotalSumSquaredError:
                MinTotalSumSquaredError = TotalSumSquaredError
                BestWidth = Width
        print("found best")
        self.get_fit_from_peak(CentralFreq - BestWidth / 2,
                               CentralFreq + BestWidth / 2, ShowFig=ShowFig)
        FTrap = self.Ftrap
        A = self.A
        Gamma = self.Gamma
        return FTrap, A, Gamma

    def extract_parameters(self, P_mbar, P_Error):
        """
        Extracts the Radius  mass and Conversion factor for a particle.

        Parameters
        ----------
        P_mbar : float 
            The pressure in mbar when the data was taken.
        P_Error : float
            The error in the pressure value (as a decimal e.g. 15% = 0.15)
        
        Returns
        -------
        Radius : uncertainties.ufloat
            The radius of the particle in m
        Mass : uncertainties.ufloat
            The mass of the particle in kg
        ConvFactor : uncertainties.ufloat
            The conversion factor between volts/m
        """

        [R, M, ConvFactor], [RErr, MErr, ConvFactorErr] = \
            extract_parameters(P_mbar, P_Error,
                               self.A.n, self.A.std_dev,
                               self.Gamma.n, self.Gamma.std_dev)
        self.Radius = _uncertainties.ufloat(R, RErr)
        self.Mass = _uncertainties.ufloat(M, MErr)
        self.ConvFactor = _uncertainties.ufloat(ConvFactor, ConvFactorErr)

        return self.Radius, self.Mass, self.ConvFactor

    def extract_ZXY_motion(self, ApproxZXYFreqs, uncertaintyInFreqs, ZXYPeakWidths, subSampleFraction=1):
        """
        Extracts the x, y and z signals (in volts) from the voltage signal. Does this by finding the highest peaks in the signal about the approximate frequencies, using the uncertaintyinfreqs parameter as the width it searches. It then uses the ZXYPeakWidths to construct bandpass IIR filters for each frequency and filtering them. If too high a sample frequency has been used to collect the data scipy may not be able to construct a filter good enough, in this case increasing the subSampleFraction may be nessesary.
        
        Parameters
        ----------
        ApproxZXYFreqs : array_like
            A sequency containing 3 elements, the approximate 
            z, x and y frequency respectively.
        uncertaintyInFreqs : array_like
            A sequency containing 3 elements, the uncertainty in the
            z, x and y frequency respectively.
        ZXYPeakWidths : array_like
            A sequency containing 3 elements, the widths of the
            z, x and y frequency peaks respectively.
        subSampleFraction : int, optional
            How much to sub-sample the data by before filtering,
            effectively reducing the sample frequency by this 
            fraction.

        Returns
        -------
        self.zVolts : ndarray
            The z signal in volts extracted by bandpass IIR filtering
        self.xVolts : ndarray
            The x signal in volts extracted by bandpass IIR filtering
        self.yVolts : ndarray
            The y signal in volts extracted by bandpass IIR filtering        """
        [zf, xf, yf] = ApproxZXYFreqs
        zf, xf, yf = get_ZXY_freqs(
            self, zf, xf, yf, bandwidth=uncertaintyInFreqs)
        #print(zf, xf, yf)
        [zwidth, xwidth, ywidth] = ZXYPeakWidths
        self.zVolts, self.xVolts, self.yVolts = get_ZXY_data(
            self, zf, xf, yf, subSampleFraction, zwidth, xwidth, ywidth)
        return self.zVolts, self.xVolts, self.yVolts

    def plot_phase_space(self, zf, xf=80000, yf=120000, FractionOfSampleFreq=4, zwidth=10000, xwidth=5000, ywidth=5000, ShowFig=True):
        """
        author: Markus Rademacher
        """
        Z, X, Y, Time = get_ZXY_data(
            self, zf, xf, yf, FractionOfSampleFreq, zwidth, xwidth, ywidth, ShowFig=False)

        conv = self.ConvFactor.n
        ZArray = Z / conv
        ZVArray = _np.diff(ZArray) * (self.SampleFreq / FractionOfSampleFreq)
        VarZ = _np.var(ZArray)
        VarZV = _np.var(ZVArray)
        MaxZ = _np.max(ZArray)
        MaxZV = _np.max(ZVArray)
        if MaxZ > MaxZV / (2 * _np.pi * zf):
            _plotlimit = MaxZ * 1.1
        else:
            _plotlimit = MaxZV / (2 * _np.pi * zf) * 1.1

        JP1 = _sns.jointplot(_pd.Series(ZArray[1:], name="$z$(m) \n filepath=%s" % (self.filepath)), _pd.Series(
            ZVArray / (2 * _np.pi * zf), name="$v_z$/$\omega$(m)"), stat_func=None, xlim=[-_plotlimit, _plotlimit], ylim=[-_plotlimit, _plotlimit])
        JP1.ax_joint.text(_np.mean(ZArray), MaxZV / (2 * _np.pi * zf) * 1.15,
                          r"$\sigma_z=$ %.2Em, $\sigma_v=$ %.2Em" % (
                              VarZ, VarZV),
                          horizontalalignment='center')
        JP1.ax_joint.text(_np.mean(ZArray), MaxZV / (2 * _np.pi * zf) * 1.6,
                          "filepath=%s" % (self.filepath),
                          horizontalalignment='center')
        if ShowFig == True:
            _plt.show()

        return VarZ, VarZV, JP1, self.Mass

    
class ORGTableData():
    """
    Class for reading in general data from org-mode tables.


    The table must be formatted as in the example below:

    ```
    | RunNo | ColumnName1 | ColumnName2 |
    |-------+-------------+-------------|
    |   3   |     14      |     15e3    |
    ```

    In this case the run number would be 3 and the ColumnName2-value would
    be 15e3 (15000.0).

    """
    def __init__(self, filename):
        """
        Opens the org-mode table file, reads the file in as a string,
        and runs parse_orgtable in order to read the pressure.
        """
        with open(filename, 'r') as file:
            fileContents = file.readlines()
        self.ORGTableData = parse_orgtable(fileContents)

    def get_value(self, ColumnName, RunNo):
        """
        Retreives the value of the collumn named ColumnName associated 
        with a particular run number.

        Parameters
        ----------
        ColumnName : string
            The name of the desired org-mode table's collumn

        RunNo : int
            The run number for which to retreive the pressure value
        
        Returns
        -------
        Value : float
            The value for the column's name and associated run number
        """
        Value = float(self.ORGTableData[self.ORGTableData.RunNo == '{}'.format(
            RunNo)][ColumnName])
        
        return Value 
    
def load_data(Filepath):
    """
    Parameters
    ----------
        Filepath : string
            filepath to the file containing the data used to initialise
            and create an instance of the DataObject class

    Returns
    -------
        Data : DataObject
            An instance of the DataObject class contaning the data
            that you requested to be loaded.
    """
    print("Loading data from {}".format(Filepath))
    return DataObject(Filepath)


def multi_load_data(Channel, RunNos, RepeatNos, directoryPath='.'):
    """
    Lets you load multiple datasets at once.

    Parameters
    ----------
    Channel : int
        The channel you want to load
    RunNos : sequence
        Sequence of run numbers you want to load
    RepeatNos : sequence
        Sequence of repeat numbers you want to load
    directoryPath : string, optional
        The path to the directory housing the data
        The default is the current directory

    Returns
    -------
    Data : list
        A list containing the DataObjects that were loaded. 
    """
    files = glob('{}/*'.format(directoryPath))
    files_CorrectChannel = []
    for file_ in files:
        if 'CH{}'.format(Channel) in file_:
            files_CorrectChannel.append(file_)
    files_CorrectRunNo = []
    for RunNo in RunNos:
        files_match = _fnmatch.filter(
            files_CorrectChannel, '*RUN*0{}_*'.format(RunNo))
        for file_ in files_match:
            files_CorrectRunNo.append(file_)
    files_CorrectRepeatNo = []
    for RepeatNo in RepeatNos:
        files_match = _fnmatch.filter(
            files_CorrectRunNo, '*REPEAT*0{}.*'.format(RepeatNo))
        for file_ in files_match:
            files_CorrectRepeatNo.append(file_)
    cpu_count = _cpu_count()
    workerPool = _Pool(cpu_count)
    # for filepath in files_CorrectRepeatNo:
    #    print(filepath)
    #    data.append(load_data(filepath))
    data = workerPool.map(load_data, files_CorrectRepeatNo)
    return data

def calc_temp(Data_ref, Data):
    """
    Calculates the temperature of a data set relative to a reference.
    The reference is assumed to be at 300K.

    Parameters
    ----------
    Data_ref : DataObject
        Reference data set, assumed to be 300K
    Data : DataObject
        Data object to have the temperature calculated for

    Returns
    -------
    T : uncertainties.ufloat
        The temperature of the data set
    """
    T = 300 * ((Data.A * Data_ref.Gamma) / (Data_ref.A * Data.Gamma))
    Data.T = T
    return T


def fit_curvefit(p0, datax, datay, function, **kwargs):
    """
    Fits the data to a function using scipy.optimise.curve_fit

    Parameters
    ----------
    p0 : array_like
        initial parameters to use for fitting
    datax : array_like
        x data to use for fitting
    datay : array_like
        y data to use for fitting
    function : function
        funcion to be fit to the data
    kwargs 
        keyword arguments to be passed to scipy.optimise.curve_fit

    Returns
    -------
    pfit_curvefit : array
        Optimal values for the parameters so that the sum of
        the squared residuals of f(xdata, *popt) - ydata is minimized
    perr_curvefit : array
        One standard deviation errors in the optimal values for
        the parameters
    """
    pfit, pcov = \
        _curve_fit(function, datax, datay, p0=p0,
                   epsfcn=0.0001, **kwargs)
    error = []
    for i in range(len(pfit)):
        try:
            error.append(_np.absolute(pcov[i][i])**0.5)
        except:
            error.append(_np.NaN)
    pfit_curvefit = pfit
    perr_curvefit = _np.array(error)
    return pfit_curvefit, perr_curvefit


def moving_average(array, n=3):
    """
    Calculates the moving average of an array.

    Parameters
    ----------
    array : array
        The array to have the moving average taken of
    n : int
        The number of points of moving average to take
    
    Returns
    -------
    MovingAverageArray : array
        The n-point moving average of the input array
    """
    ret = _np.cumsum(array, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    return ret[n - 1:] / n


def take_closest(myList, myNumber):
    """
    Assumes myList is sorted. Returns closest value to myNumber.
    If two numbers are equally close, return the smallest number.

    Parameters
    ----------
    myList : array
        The list in which to find the closest value to myNumber
    myNumber : float
        The number to find the closest to in MyList

    Returns
    -------
    closestValue : float
        The number closest to myNumber in myList
    """
    pos = _bisect_left(myList, myNumber)
    if pos == 0:
        return myList[0]
    if pos == len(myList):
        return myList[-1]
    before = myList[pos - 1]
    after = myList[pos]
    if after - myNumber < myNumber - before:
        return after
    else:
        return before


def _PSD_fitting_eqn(A, OmegaTrap, gamma, omega):
    """
    The value of the fitting equation:
    A / ((OmegaTrap**2 - omega**2)**2 + (omega * gamma)**2)
    to be fit to the PSD

    Parameters
    ----------
    A : float
        Fitting constant A
        A = γ**2*Γ_0*(K_b*T_0)/(π*m)
        where:
            γ = conversionFactor
            Γ_0 = Damping factor due to environment
            π = pi
    OmegaTrap : float
        The trapping frequency in the axis of interest 
        (in angular frequency)
    Gamma : float
        The damping factor Gamma = Γ = Γ_0 + δΓ
        where:
            Γ_0 = Damping factor due to environment
            δΓ = extra damping due to feedback or other effects
    omega : float
        The angular frequency to calculate the value of the 
        fitting equation at 

    Returns
    -------
    Value : float
        The value of the fitting equation
    """
    return A / ((OmegaTrap**2 - omega**2)**2 + (omega * gamma)**2)


def fit_PSD(Data, bandwidth, NMovAve, TrapFreqGuess, AGuess=0.1e10, GammaGuess=400, MakeFig=True, ShowFig=True):
    """
    Fits theory PSD to Data. Assumes highest point of PSD is the
    trapping frequency.

    Parameters
    ----------
    Data : DataObject
        data object to be fitted
    bandwidth : float
         bandwidth around trapping frequency peak to
         fit the theory PSD to
    NMovAve : integer
         amount of moving averages to take before the fitting
    TrapFreqGuess : float
        The approximate trapping frequency to use initially
        as the centre of the peak
    AGuess : float, optional
        The initial value of the A parameter to use in fitting
    GammaGuess : float, optional
        The initial value of the Gamma parameter to use in fitting
    MakeFig : bool, optional
        Whether to construct and return the figure object showing
        the fitting. defaults to True
    ShowFig : bool, optional
        Whether to show the figure object when it has been created.
        defaults to True

    Returns
    -------
    ParamsFit - Fitted parameters:
        [A, TrappingFrequency, Gamma]
    ParamsFitErr - Error in fitted parameters:
        [AErr, TrappingFrequencyErr, GammaErr]
    fig : matplotlib.figure.Figure object
        figure object containing the plot
    ax : matplotlib.axes.Axes object
        axes with the data plotted of the:
            - initial data
            - smoothed data
            - initial fit
            - final fit
    """
    AngFreqs = 2 * _np.pi * Data.freqs
    Angbandwidth = 2 * _np.pi * bandwidth
    AngTrapFreqGuess = 2 * _np.pi * TrapFreqGuess

    ClosestToAngTrapFreqGuess = take_closest(AngFreqs, AngTrapFreqGuess)
    index_ftrap = _np.where(AngFreqs == ClosestToAngTrapFreqGuess)
    ftrap = AngFreqs[index_ftrap]

    f_fit_lower = take_closest(AngFreqs, ftrap - Angbandwidth / 2)
    f_fit_upper = take_closest(AngFreqs, ftrap + Angbandwidth / 2)

    indx_fit_lower = int(_np.where(AngFreqs == f_fit_lower)[0])
    indx_fit_upper = int(_np.where(AngFreqs == f_fit_upper)[0])

#    print(f_fit_lower, f_fit_upper)
#    print(AngFreqs[indx_fit_lower], AngFreqs[indx_fit_upper])

    # find highest point in region about guess for trap frequency - use that
    # as guess for trap frequency and recalculate region about the trap
    # frequency
    index_ftrap = _np.where(Data.PSD == max(
        Data.PSD[indx_fit_lower:indx_fit_upper]))

    ftrap = AngFreqs[index_ftrap]

#    print(ftrap)

    f_fit_lower = take_closest(AngFreqs, ftrap - Angbandwidth / 2)
    f_fit_upper = take_closest(AngFreqs, ftrap + Angbandwidth / 2)

    indx_fit_lower = int(_np.where(AngFreqs == f_fit_lower)[0])
    indx_fit_upper = int(_np.where(AngFreqs == f_fit_upper)[0])

    PSD_smoothed = moving_average(Data.PSD, NMovAve)
    freqs_smoothed = moving_average(AngFreqs, NMovAve)

    logPSD_smoothed = 10 * _np.log10(PSD_smoothed)

    def calc_theory_PSD_curve_fit(freqs, A, TrapFreq, BigGamma):
        Theory_PSD = 10 * \
            _np.log10(_PSD_fitting_eqn(A, TrapFreq, BigGamma, freqs))
        if A < 0 or TrapFreq < 0 or BigGamma < 0:
            return 1e9
        else:
            return Theory_PSD

    datax = freqs_smoothed[indx_fit_lower:indx_fit_upper]
    datay = logPSD_smoothed[indx_fit_lower:indx_fit_upper]

    p0 = _np.array([AGuess, ftrap, GammaGuess])

    Params_Fit, Params_Fit_Err = fit_curvefit(p0,
                                              datax, datay, calc_theory_PSD_curve_fit)

    if MakeFig == True:
        fig = _plt.figure()
        ax = fig.add_subplot(111)

        PSDTheory_fit_initial = 10 * _np.log10(
            _PSD_fitting_eqn(p0[0], p0[1],
                             p0[2], freqs_smoothed))

        PSDTheory_fit = 10 * _np.log10(
            _PSD_fitting_eqn(Params_Fit[0],
                             Params_Fit[1],
                             Params_Fit[2],
                             freqs_smoothed))

        ax.plot(AngFreqs / (2 * _np.pi), Data.PSD,
                color="darkblue", label="Raw PSD Data", alpha=0.5)
        ax.plot(freqs_smoothed / (2 * _np.pi), 10**(logPSD_smoothed / 10),
                color='blue', label="smoothed", linewidth=1.5)
        ax.plot(freqs_smoothed / (2 * _np.pi), 10**(PSDTheory_fit_initial / 10),
                '--', alpha=0.7, color="purple", label="initial vals")
        ax.plot(freqs_smoothed / (2 * _np.pi), 10**(PSDTheory_fit / 10),
                color="red", label="fitted vals")
        ax.set_xlim([(ftrap - 5 * Angbandwidth) / (2 * _np.pi),
                     (ftrap + 5 * Angbandwidth) / (2 * _np.pi)])
        ax.plot([(ftrap - Angbandwidth) / (2 * _np.pi), (ftrap - Angbandwidth) / (2 * _np.pi)],
                [min(10**(logPSD_smoothed / 10)),
                 max(10**(logPSD_smoothed / 10))], '--',
                color="grey")
        ax.plot([(ftrap + Angbandwidth) / (2 * _np.pi), (ftrap + Angbandwidth) / (2 * _np.pi)],
                [min(10**(logPSD_smoothed / 10)),
                 max(10**(logPSD_smoothed / 10))], '--',
                color="grey")
        ax.semilogy()
        ax.legend(loc="best")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("$S_{xx}$ ($v^2/Hz$)")
        if ShowFig == True:
            _plt.show()
        return Params_Fit, Params_Fit_Err, fig, ax
    else:
        return Params_Fit, Params_Fit_Err, None, None


def extract_parameters(Pressure, PressureErr, A, AErr, Gamma0, Gamma0Err):
    """
    Calculates the radius, mass and conversion factor and thier uncertainties.
    For values to be correct data must have been taken with feedback off and
    at pressures of around 1mbar (this is because the equations assume
    harmonic motion and at lower pressures the uncooled particle experiences
    anharmonic motion (due to exploring furthur outside the middle of the trap).
    When cooled the value of Gamma (the damping) is a combination of the
    enviromental damping and feedback damping and so is not the correct value
    for use in this equation (as it requires the enviromental damping).
    Environmental damping can be predicted though as A=const*Gamma0. By
    fitting to 1mbar data one can find the value of the const and therefore
    Gamma0 = A/const

    Parameters
    ----------
    Pressure : float
        Pressure in mbar when the data was taken
    PressureErr : float
        Error in the Pressure as a decimal (e.g. 15% error is 0.15) 
    A : float
        Fitting constant A
        A = γ**2*Γ_0*(K_b*T_0)/(π*m)
        where:
            γ = conversionFactor
            Γ_0 = Damping factor due to environment
            π = pi
    AErr : float
        Error in Fitting constant A
    Gamma0 : float
        The enviromental damping factor Gamma_0 = Γ_0
    Gamma0Err : float
        The error in the enviromental damping factor Gamma_0 = Γ_0

    Returns:
    Params : list
        [radius, mass, conversionFactor]
        The extracted parameters
    ParamsError : list
        [radiusError, massError, conversionFactorError]
        The error in the extracted parameters
    """
    Pressure = 100 * Pressure  # conversion to Pascals

    rho = 2200  # kgm^3
    dm = 0.372e-9  # m I'Hanlon, 2003
    T0 = 300  # kelvin
    kB = 1.38e-23  # m^2 kg s^-2 K-1
    eta = 18.27e-6  # Pa s, viscosity of air

    radius = (0.169 * 9 * _np.pi * eta * dm**2) / \
        (_np.sqrt(2) * rho * kB * T0) * (Pressure) / (Gamma0)
    err_radius = radius * \
        _np.sqrt(((PressureErr * Pressure) / Pressure)
                 ** 2 + (Gamma0Err / Gamma0)**2)
    mass = rho * ((4 * _np.pi * radius**3) / 3)
    err_mass = mass * 2 * err_radius / radius
    conversionFactor = _np.sqrt(A * _np.pi * mass / (kB * T0 * Gamma0))
    err_conversionFactor = conversionFactor * \
        _np.sqrt((AErr / A)**2 + (err_mass / mass)
                 ** 2 + (Gamma0Err / Gamma0)**2)

    return [radius, mass, conversionFactor], [err_radius, err_mass, err_conversionFactor]


def get_ZXY_freqs(Data, zfreq, xfreq, yfreq, bandwidth=5000):
    """
    Determines the exact z, x and y peak frequencies from approximate
    frequencies by finding the highest peak in the PSD "close to" the
    approximate peak frequency. By "close to" I mean within the range:
    approxFreq - bandwidth/2 to approxFreq + bandwidth/2

    Parameters
    ----------
    Data : DataObject
        DataObject containing the data for which you want to determine the
        z, x and y frequencies.
    zfreq : float
        An approximate frequency for the z peak
    xfreq : float
        An approximate frequency for the z peak
    yfreq : float
        An approximate frequency for the z peak
    bandwidth : float, optional
        The bandwidth around the approximate peak to look for the actual peak. The default value is 5000

    Returns
    -------
    trapfreqs : list
        List containing the trap frequencies in the following order (z, x, y)
    """
    trapfreqs = []
    for freq in [zfreq, xfreq, yfreq]:
        z_f_fit_lower = take_closest(Data.freqs, freq - bandwidth / 2)
        z_f_fit_upper = take_closest(Data.freqs, freq + bandwidth / 2)
        z_indx_fit_lower = int(_np.where(Data.freqs == z_f_fit_lower)[0])
        z_indx_fit_upper = int(_np.where(Data.freqs == z_f_fit_upper)[0])

        z_index_ftrap = _np.where(Data.PSD == max(
            Data.PSD[z_indx_fit_lower:z_indx_fit_upper]))
        # find highest point in region about guess for trap frequency
        # use that as guess for trap frequency and recalculate region
        # about the trap frequency
        z_ftrap = Data.freqs[z_index_ftrap]
        trapfreqs.append(z_ftrap)
    return trapfreqs


def get_ZXY_data(Data, zf, xf, yf, FractionOfSampleFreq=1,
                 zwidth=10000, xwidth=5000, ywidth=5000,
                 ztransition=10000, xtransition=5000, ytransition=5000,
                 filterImplementation="filtfilt",
                 timeStart="Default", timeEnd="Default",
                 ShowFig=True):
    """
    Given a Data object and the frequencies of the z, x and y peaks (and some
    optional parameters for the created filters) this function extracts the
    individual z, x and y signals (in volts) by creating IIR filters and filtering
    the Data.

    Parameters
    ----------
    Data : DataObject
        DataObject containing the data for which you want to extract the
        z, x and y signals.
    zf : float
        The frequency of the z peak in the PSD
    xf : float
        The frequency of the x peak in the PSD
    yf : float
        The frequency of the y peak in the PSD
    FractionOfSampleFreq : integer, optional
        The fraction of the sample frequency to sub-sample the data by.
        This sometimes needs to be done because a filter with the appropriate
        frequency response may not be generated using the sample rate at which
        the data was taken. Increasing this number means the x, y and z signals
        produced by this function will be sampled at a lower rate but a higher
        number means a higher chance that the filter produced will have a nice
        frequency response.
    zwidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter Z.
    xwidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter X.
    ywidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter Y.
    ztransition : float, optional
        The width of the transition-band of the IIR filter to be generated to
        filter Z.
    xtransition : float, optional
        The width of the transition-band of the IIR filter to be generated to
        filter X.
    ytransition : float, optional
        The width of the transition-band of the IIR filter to be generated to
        filter Y.
    filterImplementation : string, optional
        filtfilt or lfilter - use scipy.filtfilt or lfilter
        default: filtfilt
    timeStart : float, optional
        Starting time for filtering
    timeEnd : float, optional
        Ending time for filtering
    ShowFig : bool, optional
        If True - plot unfiltered and filtered PSD for z, x and y.
        If False - don't plot anything

    Returns
    -------
    zdata : ndarray
        Array containing the z signal in volts with time.
    xdata : ndarray
        Array containing the x signal in volts with time.
    ydata : ndarray
        Array containing the y signal in volts with time.
    timedata : ndarray
        Array containing the time data to go with the z, x, and y signal.
    """
    if timeStart == "Default":
        timeStart = Data.time[0]
    if timeEnd == "Default":
        timeEnd = Data.time[-1]

    StartIndex = list(Data.time).index(take_closest(Data.time, timeStart))
    EndIndex = list(Data.time).index(take_closest(Data.time, timeEnd))

    SAMPLEFREQ = Data.SampleFreq / FractionOfSampleFreq

    if filterImplementation == "filtfilt":
        ApplyFilter = scipy.signal.filtfilt
    elif filterImplementation == "lfilter":
        ApplyFilter = scipy.signal.lfilter
    else:
        raise ValueError("filterImplementation must be one of [filtfilt, lfilter] you entered: {}".format(
            filterImplementation))

    input_signal = Data.voltage[StartIndex: EndIndex][0::FractionOfSampleFreq]

    bZ, aZ = IIRFilterDesign(zf, zwidth, ztransition, SAMPLEFREQ, GainStop=100)

    zdata = ApplyFilter(bZ, aZ, input_signal)

    if(_np.isnan(zdata).any()):
        raise ValueError(
            "Value Error: FractionOfSampleFreq must be higher, a sufficiently small sample frequency should be used to produce a working IIR filter.")

    bX, aX = IIRFilterDesign(xf, xwidth, xtransition, SAMPLEFREQ, GainStop=100)

    xdata = ApplyFilter(bX, aX, input_signal)

    if(_np.isnan(xdata).any()):
        raise ValueError(
            "Value Error: FractionOfSampleFreq must be higher, a sufficiently small sample frequency should be used to produce a working IIR filter.")

    bY, aY = IIRFilterDesign(yf, ywidth, ytransition, SAMPLEFREQ, GainStop=100)

    ydata = ApplyFilter(bY, aY, input_signal)

    if(_np.isnan(ydata).any()):
        raise ValueError(
            "Value Error: FractionOfSampleFreq must be higher, a sufficiently small sample frequency should be used to produce a working IIR filter.")

    if ShowFig == True:
        NPerSegment = len(Data.time)
        if NPerSegment > 1e5:
            NPerSegment = int(1e5)
        f, PSD = scipy.signal.welch(
            input_signal, SAMPLEFREQ, nperseg=NPerSegment)
        f_z, PSD_z = scipy.signal.welch(zdata, SAMPLEFREQ, nperseg=NPerSegment)
        f_y, PSD_y = scipy.signal.welch(ydata, SAMPLEFREQ, nperseg=NPerSegment)
        f_x, PSD_x = scipy.signal.welch(xdata, SAMPLEFREQ, nperseg=NPerSegment)
        _plt.plot(f, PSD)
        _plt.plot(f_z, PSD_z, label="z")
        _plt.plot(f_x, PSD_x, label="x")
        _plt.plot(f_y, PSD_y, label="y")
        _plt.legend(loc="best")
        _ply.semilogy
        _plt.xlim([zf - zwidth - ztransition, yf + ywidth + ytransition])
        _plt.show()

    timedata = Data.time[StartIndex: EndIndex][0::FractionOfSampleFreq]
    return zdata, xdata, ydata, timedata


def get_ZXY_data_IFFT(Data, zf, xf, yf,
                      zwidth=10000, xwidth=5000, ywidth=5000,
                      timeStart="Default", timeEnd="Default",
                      ShowFig=True):
    """
    Given a Data object and the frequencies of the z, x and y peaks (and some
    optional parameters for the created filters) this function extracts the
    individual z, x and y signals (in volts) by creating IIR filters and filtering
    the Data.

    Parameters
    ----------
    Data : DataObject
        DataObject containing the data for which you want to extract the
        z, x and y signals.
    zf : float
        The frequency of the z peak in the PSD
    xf : float
        The frequency of the x peak in the PSD
    yf : float
        The frequency of the y peak in the PSD
    zwidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter Z.
    xwidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter X.
    ywidth : float, optional
        The width of the pass-band of the IIR filter to be generated to
        filter Y.
    timeStart : float, optional
        Starting time for filtering
    timeEnd : float, optional
        Ending time for filtering
    ShowFig : bool, optional
        If True - plot unfiltered and filtered PSD for z, x and y.
        If False - don't plot anything

    Returns
    -------
    zdata : ndarray
        Array containing the z signal in volts with time.
    xdata : ndarray
        Array containing the x signal in volts with time.
    ydata : ndarray
        Array containing the y signal in volts with time.
    timedata : ndarray
        Array containing the time data to go with the z, x, and y signal.
    """
    if timeStart == "Default":
        timeStart = Data.time[0]
    if timeEnd == "Default":
        timeEnd = Data.time[-1]

    StartIndex = list(Data.time).index(take_closest(Data.time, timeStart))
    EndIndex = list(Data.time).index(take_closest(Data.time, timeEnd))

    SAMPLEFREQ = Data.SampleFreq

    input_signal = Data.voltage[StartIndex: EndIndex]

    zdata = IFFT_filter(input_signal, SAMPLEFREQ, zf -
                        zwidth / 2, zf + zwidth / 2)

    xdata = IFFT_filter(input_signal, SAMPLEFREQ, xf -
                        zwidth / 2, xf + zwidth / 2)

    ydata = IFFT_filter(input_signal, SAMPLEFREQ, yf -
                        zwidth / 2, yf + zwidth / 2)

    if ShowFig == True:
        NPerSegment = len(Data.time)
        if NPerSegment > 1e5:
            NPerSegment = int(1e5)
        f, PSD = scipy.signal.welch(
            input_signal, SAMPLEFREQ, nperseg=NPerSegment)
        f_z, PSD_z = scipy.signal.welch(zdata, SAMPLEFREQ, nperseg=NPerSegment)
        f_y, PSD_y = scipy.signal.welch(ydata, SAMPLEFREQ, nperseg=NPerSegment)
        f_x, PSD_x = scipy.signal.welch(xdata, SAMPLEFREQ, nperseg=NPerSegment)
        _plt.plot(f, PSD)
        _plt.plot(f_z, PSD_z, label="z")
        _plt.plot(f_x, PSD_x, label="x")
        _plt.plot(f_y, PSD_y, label="y")
        _plt.legend(loc="best")
        _plt.xlim([zf - zwidth, yf + ywidth])
        _plt.xlabel('Frequency (Hz)')
        _plt.ylabel(r'$S_{xx}$')
        _plt.semilogy()
        _plt.title("filepath = %s" % (Data.filepath))
        _plt.show()

    timedata = Data.time[StartIndex: EndIndex]
    return zdata, xdata, ydata, timedata


def animate(zdata, xdata, ydata,
            conversionFactor, timedata,
            BoxSize,
            timeSteps=100, filename="particle"):
    """
    Animates the particle's motion given the z, x and y signal (in Volts)
    and the conversion factor (to convert between V and nm).

    Parameters
    ----------
    zdata : ndarray
        Array containing the z signal in volts with time.
    xdata : ndarray
        Array containing the x signal in volts with time.
    ydata : ndarray
        Array containing the y signal in volts with time.
    conversionFactor : float
        conversion factor (in units of Volts/Metre)
    timedata : ndarray
        Array containing the time data in seconds.
    BoxSize : float
        The size of the box in which to animate the particle - in nm
    timeSteps : int, optional
        Number of time steps to animate
    filename : string, optional
        filename to create the mp4 under (<filename>.mp4)

    """
    timePerFrame = 0.203
    print("This will take ~ {} minutes".format(timePerFrame * timeSteps / 60))

    conv = conversionFactor * 1e-9

    ZBoxStart = -BoxSize  # 1/conv*(_np.mean(zdata)-0.06)
    ZBoxEnd = BoxSize  # 1/conv*(_np.mean(zdata)+0.06)
    XBoxStart = -BoxSize  # 1/conv*(_np.mean(xdata)-0.06)
    XBoxEnd = BoxSize  # 1/conv*(_np.mean(xdata)+0.06)
    YBoxStart = -BoxSize  # 1/conv*(_np.mean(ydata)-0.06)
    YBoxEnd = BoxSize  # 1/conv*(_np.mean(ydata)+0.06)

    FrameInterval = 1  # how many timesteps = 1 frame in animation

    a = 20
    b = 0.6 * a
    myFPS = 7
    myBitrate = 1e6

    fig = _plt.figure(figsize=(a, b))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title("{} us".format(timedata[0] * 1e6))
    ax.set_xlabel('X (nm)')
    ax.set_xlim([XBoxStart, XBoxEnd])
    ax.set_ylabel('Y (nm)')
    ax.set_ylim([YBoxStart, YBoxEnd])
    ax.set_zlabel('Z (nm)')
    ax.set_zlim([ZBoxStart, ZBoxEnd])
    ax.view_init(20, -30)

    #ax.view_init(0, 0)

    def setup_plot():
        XArray = 1 / conv * xdata[0]
        YArray = 1 / conv * ydata[0]
        ZArray = 1 / conv * zdata[0]
        scatter = ax.scatter(XArray, YArray, ZArray)
        return scatter,

    def animate(i):
        # print "\r {}".format(i),
        print("Frame: {}".format(i), end="\r")
        ax.clear()
        ax.view_init(20, -30)
        ax.set_title("{} us".format(timedata[i] * 1e6))
        ax.set_xlabel('X (nm)')
        ax.set_xlim([XBoxStart, XBoxEnd])
        ax.set_ylabel('Y (nm)')
        ax.set_ylim([YBoxStart, YBoxEnd])
        ax.set_zlabel('Z (nm)')
        ax.set_zlim([ZBoxStart, ZBoxEnd])
        XArray = 1 / conv * xdata[i]
        YArray = 1 / conv * ydata[i]
        ZArray = 1 / conv * zdata[i]
        scatter = ax.scatter(XArray, YArray, ZArray)
        ax.scatter([XArray], [0], [-ZBoxEnd], c='k', alpha=0.9)
        ax.scatter([-XBoxEnd], [YArray], [0], c='k', alpha=0.9)
        ax.scatter([0], [YBoxEnd], [ZArray], c='k', alpha=0.9)

        Xx, Yx, Zx, Xy, Yy, Zy, Xz, Yz, Zz = [], [], [], [], [], [], [], [], []

        for j in range(0, 30):

            Xlast = 1 / conv * xdata[i - j]
            Ylast = 1 / conv * ydata[i - j]
            Zlast = 1 / conv * zdata[i - j]

            Alpha = 0.5 - 0.05 * j
            if Alpha > 0:
                ax.scatter([Xlast], [0 + j * 10],
                           [-ZBoxEnd], c='grey', alpha=Alpha)
                ax.scatter([-XBoxEnd], [Ylast], [0 - j * 10],
                           c='grey', alpha=Alpha)
                ax.scatter([0 - j * 2], [YBoxEnd],
                           [Zlast], c='grey', alpha=Alpha)

                Xx.append(Xlast)
                Yx.append(0 + j * 10)
                Zx.append(-ZBoxEnd)

                Xy.append(-XBoxEnd)
                Yy.append(Ylast)
                Zy.append(0 - j * 10)

                Xz.append(0 - j * 2)
                Yz.append(YBoxEnd)
                Zz.append(Zlast)

            if j < 15:
                XCur = 1 / conv * xdata[i - j + 1]
                YCur = 1 / conv * ydata[i - j + 1]
                ZCur = 1 / conv * zdata[i - j + 1]
                ax.plot([Xlast, XCur], [Ylast, YCur], [Zlast, ZCur], alpha=0.4)

        ax.plot_wireframe(Xx, Yx, Zx, color='grey')
        ax.plot_wireframe(Xy, Yy, Zy, color='grey')
        ax.plot_wireframe(Xz, Yz, Zz, color='grey')

        return scatter,

    anim = _animation.FuncAnimation(fig, animate, int(
        timeSteps / FrameInterval), init_func=setup_plot, blit=True)

    _plt.rcParams['animation.ffmpeg_path'] = '/usr/bin/ffmpeg'
    mywriter = _animation.FFMpegWriter(fps=myFPS, bitrate=myBitrate)
    # , fps = myFPS, bitrate = myBitrate)
    anim.save('{}.mp4'.format(filename), writer=mywriter)
    return None

def IFFT_filter(Signal, SampleFreq, lowerFreq, upperFreq):
    """
    Filters data using fft -> zeroing out fft bins -> ifft

    Parameters
    ----------
    Signal : ndarray
        Signal to be filtered
    SampleFreq : float
        Sample frequency of signal
    lowerFreq : float
        Lower frequency of bandpass to allow through filter
    upperFreq : float
       Upper frequency of bandpass to allow through filter

    Returns
    -------
    FilteredData : ndarray
        Array containing the filtered data
    """
    print("starting fft")
    Signalfft = scipy.fftpack.fft(Signal)
    print("starting freq calc")
    freqs = _np.fft.fftfreq(len(Signal)) * SampleFreq
    print("starting bin zeroing")
    for i, freq in enumerate(freqs):
        if freq < lowerFreq or freq > upperFreq:
            Signalfft[i] = 0
    print("starting ifft")
    FilteredSignal = 2 * scipy.fftpack.ifft(Signalfft)
    print("done")
    return _np.real(FilteredSignal)


def IIR_filter_design(CentralFreq, bandwidth, transitionWidth, SampleFreq, GainStop=40, GainPass=0.01):
    """
    Function to calculate the coefficients of an IIR filter.

    Parameters
    ----------
    CentralFreq : float
        Central frequency of the IIR filter to be designed
    bandwidth : float
        The width of the passband to be created about the central frequency
    transitionWidth : float
        The width of the transition band between the pass-band and stop-band
    SampleFreq : float
        The sample frequency (rate) of the data to be filtered
    GainStop : float, optional
        The dB of attenuation within the stopband (i.e. outside the passband)
    GainPass : float, optional
        The dB attenuation inside the passband (ideally close to 0 for a bandpass filter)

    Returns
    -------
    b : ndarray
        coefficients multiplying the current and past inputs (feedforward coefficients)
    a : ndarray
        coefficients multiplying the past outputs (feedback coefficients)
    """
    NyquistFreq = SampleFreq / 2
    if (CentralFreq + bandwidth / 2 + transitionWidth > NyquistFreq):
        raise ValueError(
            "Need a higher Sample Frequency for this Central Freq, Bandwidth and transition Width")

    CentralFreqNormed = CentralFreq / NyquistFreq
    bandwidthNormed = bandwidth / NyquistFreq
    transitionWidthNormed = transitionWidth / NyquistFreq
    bandpass = [CentralFreqNormed - bandwidthNormed /
                2, CentralFreqNormed + bandwidthNormed / 2]
    bandstop = [CentralFreqNormed - bandwidthNormed / 2 - transitionWidthNormed,
                CentralFreqNormed + bandwidthNormed / 2 + transitionWidthNormed]
    print(bandpass, bandstop)
    b, a = scipy.signal.iirdesign(bandpass, bandstop, GainPass, GainStop)
    return b, a


#def IIR_filter_design_New(Order, btype, CriticalFreqs, SampleFreq, StopbandAttenuation=40, ftype='cheby2'):
#    """
#    Function to calculate the coefficients of an IIR filter.
#
#    Parameters
#    ----------
#    CentralFreq : float
#        Central frequency of the IIR filter to be designed
#    bandwidth : float
#        The width of the passband to be created about the central frequency
#    transitionWidth : float
#        The width of the transition band between the pass-band and stop-band
#    SampleFreq : float
#        The sample frequency (rate) of the data to be filtered
#    GainStop : float
#        The dB of attenuation within the stopband (i.e. outside the passband)
#    GainPass : float
#        The dB attenuation inside the passband (ideally close to 0 for a bandpass filter)
#
#    Returns
#    -------
#    b : ndarray
#        coefficients multiplying the current and past inputs (feedforward coefficients)
#    a : ndarray
#        coefficients multiplying the past outputs (feedback coefficients)
#    """
#    NyquistFreq = SampleFreq / 2
#    if len(CriticalFreqs) > 1:
#        if (CriticalFreqs[1] > NyquistFreq):
#            raise ValueError(
#                "Need a higher Sample Frequency for this Frequency range")
#
#        BandStartNormed = CriticalFreqs[0] / NyquistFreq
#        BandStopNormed = CriticalFreqs[1] / NyquistFreq
#
#        bandpass = [BandStartNormed, BandStopNormed]
#
#        b, a = scipy.signal.iirfilter(Order, bandpass, rs=StopbandAttenuation,
#                                      btype=btype, analog=False, ftype=ftype)
#    else:
#        CriticalFreq = CriticalFreqs[0]
#
#        if (CriticalFreq > NyquistFreq):
#            raise ValueError(
#                "Need a higher Sample Frequency for this Critical Frequency")
#
#        CriticalFreqNormed = CriticalFreq / NyquistFreq
#
#        b, a = scipy.signal.iirfilter(Order, CriticalFreqNormed, rs=StopbandAttenuation,
#                                      btype=btype, analog=False, ftype=ftype)
#
#    return b, a


def get_freq_response(a, b, ShowFig=True, SampleFreq=(2 * _np.pi), NumOfFreqs=500, whole=False):
    """
    This function takes an array of coefficients and finds the frequency
    response of the filter using scipy.signal.freqz.
    ShowFig sets if the response should be plotted

    Parameters
    ----------
    b : array_like
        Coefficients multiplying the x values (inputs of the filter)

    a : array_like
        Coefficients multiplying the y values (outputs of the filter)
    ShowFig : bool, optional
        Verbosity of function (i.e. whether to plot frequency and phase
        response or whether to just return the values.)
        Options (Default is 1):
        False - Do not plot anything, just return values
        True - Plot Frequency and Phase response and return values
    SampleFreq : float, optional
        Sample frequency (in Hz) to simulate (used to convert frequency range
        to normalised frequency range)
    NumOfFreqs : int, optional
        Number of frequencies to use to simulate the frequency and phase
        response of the filter. Default is 500.
    Whole : bool, optional
        Sets whether to plot the whole response (0 to sample freq)
        or just to plot 0 to Nyquist (SampleFreq/2): 
        False - (default) plot 0 to Nyquist (SampleFreq/2)
        True - plot the whole response (0 to sample freq)

    Returns
    -------
    freqList : ndarray
        Array containing the frequencies at which the gain is calculated
    GainArray : ndarray
        Array containing the gain in dB of the filter when simulated
        (20*log_10(A_out/A_in))
    PhaseDiffArray : ndarray
        Array containing the phase response of the filter - phase
        difference between the input signal and output signal at
        different frequencies
    """
    w, h = scipy.signal.freqz(b=b, a=a, worN=NumOfFreqs, whole=whole)
    freqList = w / (_np.pi) * SampleFreq / 2.0
    himag = _np.array([hi.imag for hi in h])
    GainArray = 20 * _np.log10(_np.abs(h))
    PhaseDiffArray = _np.unwrap(_np.arctan2(_np.imag(h), _np.real(h)))
    if ShowFig == True:
        fig1 = _plt.figure()
        ax = fig1.add_subplot(111)
        ax.plot(freqList, GainArray, '-', label="Specified Filter")
        ax.set_title("Frequency Response")
        if SampleFreq == 2 * _np.pi:
            ax.set_xlabel(("$\Omega$ - Normalized frequency "
                           "($\pi$=Nyquist Frequency)"))
        else:
            ax.set_xlabel("frequency (Hz)")
        ax.set_ylabel("Gain (dB)")
        ax.set_xlim([0, SampleFreq / 2.0])
        _plt.show()
        fig2 = _plt.figure()
        ax = fig2.add_subplot(111)
        ax.plot(freqList, PhaseDiffArray, '-', label="Specified Filter")
        ax.set_title("Phase Response")
        if SampleFreq == 2 * _np.pi:
            ax.set_xlabel(("$\Omega$ - Normalized frequency "
                           "($\pi$=Nyquist Frequency)"))
        else:
            ax.set_xlabel("frequency (Hz)")

        ax.set_ylabel("Phase Difference")
        ax.set_xlim([0, SampleFreq / 2.0])
        _plt.show()

    return freqList, GainArray, PhaseDiffArray


def multi_plot_PSD(DataArray, xlim=[0, 500e3], LabelArray=[], ShowFig=True):
    """
    plot the pulse spectral density for multiple data sets on the same
    axes.

    Parameters
    ----------
    DataArray - array-like
        array of DataObject instances for which to plot the PSDs
    xlim - array-like, optional
        2 element array specifying the lower and upper x limit for which to
        plot the Power Spectral Density
    LabelArray - array-like, optional
        array of labels for each data-set to be plotted
    ShowFig : bool, optional
       If True runs plt.show() before returning figure
       if False it just returns the figure object.
       (the default is True, it shows the figure)

    Returns
    -------
    fig : matplotlib.figure.Figure object
        The figure object created
    ax : matplotlib.axes.Axes object
        The axes object created
    """
    if LabelArray == []:
        LabelArray = ["DataSet {}".format(i)
                      for i in _np.arange(0, len(DataArray), 1)]
    fig = _plt.figure(figsize=[10, 6])
    ax = fig.add_subplot(111)

    for i, data in enumerate(DataArray):
        ax.semilogy(data.freqs, data.PSD, alpha=0.8, label=LabelArray[i])
    ax.set_xlabel("Frequency (Hz)")
    ax.set_xlim(xlim)
    ax.grid(which="major")
    ax.legend(loc="best")
    ax.set_ylabel("PSD ($v^2/Hz$)")

    _plt.title('filedir=%s' % (DataArray[0].filedir))

    if ShowFig == True:
        _plt.show()
    return fig, ax


def multi_plot_time(DataArray, SubSampleN=1, xlim="default", ylim="default", LabelArray=[], ShowFig=True):
    """
    plot the time trace for multiple data sets on the same axes.

    Parameters
    ----------
    DataArray : array-like
        array of DataObject instances for which to plot the PSDs
    SubSampleN : int, optional
        Number of intervals between points to remove (to sub-sample data so
        that you effectively have lower sample rate to make plotting easier
        and quicker.
    xlim : array-like, optional
        2 element array specifying the lower and upper x limit for which to
        plot the time signal
    LabelArray : array-like, optional
        array of labels for each data-set to be plotted
    ShowFig : bool, optional
       If True runs plt.show() before returning figure
       if False it just returns the figure object.
       (the default is True, it shows the figure) 

    Returns
    -------
    fig : matplotlib.figure.Figure object
        The figure object created
    ax : matplotlib.axes.Axes object
        The axes object created
    """
    if LabelArray == []:
        LabelArray = ["DataSet {}".format(i)
                      for i in _np.arange(0, len(DataArray), 1)]
    fig = _plt.figure(figsize=[10, 6])
    ax = fig.add_subplot(111)

    for i, data in enumerate(DataArray):
        ax.plot(data.time[::SubSampleN], data.voltage[::SubSampleN],
                alpha=0.8, label=LabelArray[i])
    ax.set_xlabel("time (s)")
    if xlim != "default":
        ax.set_xlim(xlim)
    if ylim != "default":
        ax.set_ylim(ylim)
    ax.grid(which="major")
    ax.legend(loc="best")
    ax.set_ylabel("voltage (V)")
    if ShowFig == True:
        _plt.show()
    return fig, ax


def multi_subplots_time(DataArray, SubSampleN=1, xlim="default", ylim="default", LabelArray=[], ShowFig=True):
    """
    plot the time trace on multiple axes

    Parameters
    ----------
    DataArray : array-like
        array of DataObject instances for which to plot the PSDs
    SubSampleN : int, optional
        Number of intervals between points to remove (to sub-sample data so
        that you effectively have lower sample rate to make plotting easier
        and quicker.
    xlim : array-like, optional
        2 element array specifying the lower and upper x limit for which to
        plot the time signal
    LabelArray : array-like, optional
        array of labels for each data-set to be plotted
    ShowFig : bool, optional
       If True runs plt.show() before returning figure
       if False it just returns the figure object.
       (the default is True, it shows the figure) 

    Returns
    -------
    fig : matplotlib.figure.Figure object
        The figure object created
    axs : list of matplotlib.axes.Axes objects
        The list of axes object created
    """
    NumDataSets = len(DataArray)

    if LabelArray == []:
        LabelArray = ["DataSet {}".format(i)
                      for i in _np.arange(0, len(DataArray), 1)]

    fig, axs = _plt.subplots(NumDataSets, 1)

    for i, data in enumerate(DataArray):
        axs[i].plot(data.time[::SubSampleN], data.voltage[::SubSampleN],
                    alpha=0.8, label=LabelArray[i])
        axs[i].set_xlabel("time (s)")
        axs[i].grid(which="major")
        axs[i].legend(loc="best")
        axs[i].set_ylabel("voltage (V)")
        if xlim != "default":
            axs[i].set_xlim(xlim)
        if ylim != "default":
            axs[i].set_ylim(ylim)
    if ShowFig == True:
        _plt.show()
    return fig, axs


def calc_PSD(Signal, SampleFreq, NPerSegment='Default', window="hann"):
    """
    Extracts the pulse spectral density (PSD) from the data.

    Parameters
    ----------
    Signal : array-like
        Array containing the signal to have the PSD calculated for
    SampleFreq : float
        Sample frequency of the signal array
    NPerSegment : int, optional
        Length of each segment used in scipy.welch
        default = the Number of time points
    window : str or tuple or array_like, optional
        Desired window to use. See get_window for a list of windows
        and required parameters. If window is array_like it will be
        used directly as the window and its length will be used for
        nperseg.
        default = "hann"

    Returns
    -------
    freqs : ndarray
            Array containing the frequencies at which the PSD has been
            calculated
    PSD : ndarray
            Array containing the value of the PSD at the corresponding
            frequency value in V**2/Hz
    """
    if NPerSegment == "Default":
        NPerSegment = len(Signal)
        if NPerSegment > 1e5:
            NPerSegment = int(1e5)
    freqs, PSD = scipy.signal.welch(Signal, SampleFreq,
                                    window=window, nperseg=NPerSegment)
    PSD = PSD[freqs.argsort()]
    freqs.sort()
    return freqs, PSD


def _GetRealImagArray(Array):
    """
    Returns the real and imaginary components of each element in an array and returns them in 2 resulting arrays.

    Parameters
    ----------
    Array : ndarray
        Input array

    Returns
    -------
    RealArray : ndarray
        The real components of the input array
    ImagArray : ndarray
        The imaginary components of the input array
    """
    ImagArray = _np.array([num.imag for num in Array])
    RealArray = _np.array([num.real for num in Array])
    return RealArray, ImagArray


def _GetComplexConjugateArray(Array):
    """
    Calculates the complex conjugate of each element in an array and returns the resulting array.

    Parameters
    ----------
    Array : ndarray
        Input array

    Returns
    -------
    ConjArray : ndarray
        The complex conjugate of the input array.
    """
    ConjArray = _np.array([num.conj() for num in Array])
    return ConjArray


def fm_discriminator(Signal):
    """
    Calculates the digital FM discriminator from a real-valued time signal.

    Parameters
    ----------
    Signal : array-like
        A real-valued time signal

    Returns
    -------
    fmDiscriminator : array-like
        The digital FM discriminator of the argument signal
    """
    S_analytic = _hilbert(Signal)
    S_analytic_star = _GetComplexConjugateArray(S_analytic)
    S_analytic_hat = S_analytic[1:] * S_analytic_star[:-1]
    R, I = _GetRealImagArray(S_analytic_hat)
    fmDiscriminator = _np.arctan2(I, R)
    return fmDiscriminator


def _approx_equal(a, b, tol):
    """
    Returns if b is approximately equal to be a within a certain percentage tolerance.

    Parameters
    ----------
    a : float
        first value
    b : float
        second value
    tol : float
        tolerance in percentage
    """
    return abs(a - b) / a * 100 < tol


def _is_this_a_collision(ArgList):
    """
    Detects if a particular point is during collision after effect (i.e. a phase shift) or not.

    Parameters
    ----------
    ArgList : array_like
        Contains the following elements:
            value : float
                value of the FM discriminator
            mean_fmd : float
                the mean value of the FM discriminator
            tolerance : float
                The tolerance in percentage that it must be away from the mean value for it
                to be counted as a collision event.

    Returns
    -------
    is_this_a_collision : bool
        True if this is a collision event, false if not.
    """
    value, mean_fmd, tolerance = ArgList
    if not _approx_equal(mean_fmd, value, tolerance):
        return True
    else:
        return False


def find_collisions(Signal, tolerance=50):
    """
    Finds collision events in the signal from the shift in phase of the signal.

    Parameters
    ----------
    Signal : array_like
        Array containing the values of the signal of interest containing a single frequency.
    tolerance : float
        Percentage tolerance, if the value of the FM Discriminator varies from the mean by this
        percentage it is counted as being during a collision event (or the aftermath of an event).

    Returns
    -------
    Collisions : ndarray
        Array of booleans, true if during a collision event, false otherwise.
    """
    fmd = fm_discriminator(Signal)
    mean_fmd = _np.mean(fmd)

    Collisions = [_is_this_a_collision(
        [value, mean_fmd, tolerance]) for value in fmd]

    return Collisions


def count_collisions(Collisions):
    """
    Counts the number of unique collisions and gets the collision index.

    Parameters
    ----------
    Collisions : array_like
        Array of booleans, containing true if during a collision event, false otherwise.

    Returns
    -------
    CollisionCount : int
        Number of unique collisions
    CollisionIndicies : list
        Indicies of collision occurance
    """
    CollisionCount = 0
    CollisionIndicies = []
    lastval = True
    for i, val in enumerate(Collisions):
        if val == True and lastval == False:
            CollisionIndicies.append(i)
            CollisionCount += 1
        lastval = val
    return CollisionCount, CollisionIndicies


def parse_orgtable(lines):
    """
    Parse an org-table (input as a list of strings split by newline)
    into a Pandas data frame.

    Parameters
    ----------
    lines : string
        an org-table input as a list of strings split by newline
    
    Returns
    -------
    dataframe : pandas.DataFrame
        A data frame containing the org-table's data
    """
    def parseline(l):
        w = l.split('|')[1:-1]
        return [wi.strip() for wi in w]
    columns = parseline(lines[0])

    data = []
    for line in lines[2:]:
        data.append(map(str, parseline(line)))
    dataframe = _pd.DataFrame(data=data, columns=columns)
    dataframe.set_index("RunNo")
    return dataframe
