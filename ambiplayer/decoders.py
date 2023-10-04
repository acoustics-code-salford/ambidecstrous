import math
import warnings
import numpy as np
import scipy.special as sp
from scipy.linalg import block_diag


class RawDecoder():
    def __init__(self, n_output_channels) -> None:
        self.n_output_channels = n_output_channels

    def decode(self, clip):
        return clip[:, :self.n_output_channels]


class UHJDecoder(RawDecoder):
    def __init__(self, n_output_channels, channel_format='ACN') -> None:
        super().__init__(n_output_channels)
        self.channel_format = channel_format

    def decode(self, clip):
        if clip.shape[1] > 4:
            warnings.warn(
                'Higher-order file input. Using first-order channels only.'
            )
            clip = clip[:, :4]
        
        clip = np.fft.fft(clip.T)

        if self.channel_format == 'ACN': W, Y, _, X = clip
        elif self.channel_format == 'FuMa': W, X, Y, _ = clip

        S = 0.9396926*W + 0.1855740*X
        D = 1j * (-0.3420201*W + 0.5098604*X) + 0.6554516*Y

        L = np.fft.ifft(((S + D)/2.0))
        R = np.fft.ifft(((S - D)/2.0))

        L = np.expand_dims(np.real(L), 1)
        R = np.expand_dims(np.real(R), 1)

        clip = np.concatenate((L, R), 1)

        # passing through super makes sure output channel count is correct
        return super().decode(clip)


class AmbisonicDecoder(RawDecoder):
    def __init__(
            self, 
            n_output_channels, 
            loudspeaker_mapping,
            N,
            channel_format='ACN',
            normalisation='SN3D',
            weighting='maxre'
    ) -> None:
        super().__init__(n_output_channels)
        n_loudspeakers = len(loudspeaker_mapping[0])
        if n_output_channels < n_loudspeakers:
            warnings.warn('Fewer output channels on device ' +
                          f'({n_output_channels}) than specified ' +
                          f'in loudspeaker mapping ({n_loudspeakers}). ' + 
                          'Output will be truncated to available channels.')

        self.N = N
        self.normalisation = normalisation
        self.channel_format = channel_format
        self.loudspeaker_mapping = loudspeaker_mapping
        self.weighting = weighting

    @property
    def normalisation(self):
        return self._normalisation
    
    @normalisation.setter
    def normalisation(self, normalisation):
        if normalisation == 'SN3D':
            self._norm = self.SN3D
        # TODO: N3D (etc.?) to go here
        self._normalisation = normalisation

    @property
    def weighting(self):
        return self._weighting
    
    @weighting.setter
    def weighting(self, weighting):
        if weighting == 'flat':
            self._w = np.ones((self._n_ambi_channels))
        elif weighting == 'maxre':
            self._w = self.max_re()
        self._weighting = weighting

    @property
    def N(self):
        return self._N
    
    @N.setter
    def N(self, N):
        self._N = N
        self._n_ambi_channels = (N+1)**2
        
        # update weighting based on order
        try: self.weighting
        except AttributeError: pass
        else:
            self.weighting = self.weighting

    @property
    def loudspeaker_mapping(self):
        return [self.channels, self.theta, self.phi]
    
    @loudspeaker_mapping.setter
    def loudspeaker_mapping(self, mapping):
        self.channels, self.theta, self.phi = mapping
        print(self.decoding_matrix(), self.decoding_matrix().shape)
    
    def decode(self, clip):
        # check and match channels to decoder order
        if clip.shape[1] > self._n_ambi_channels:
            clip = clip[:, :self._n_ambi_channels]
            warnings.warn(
                'Input file is higher order than decoder. ' +
                f'Using channels for N = {self.N} only.'
            )            
        elif clip.shape[1] < self._n_ambi_channels:
            raise ValueError(
                'Not enough channels available for selected decoder order.'
            )
        
        clip = self._w * clip @ self.decoding_matrix() 
        # passing through super makes sure output channel count is correct
        return super().decode(clip)

    def decoding_matrix(self):
        Y_mn = np.zeros([(self.N+1)**2, len(self.theta)])

        for i in range((self.N+1)**2):
            # trick from ambiX paper
            n = math.isqrt(i)
            m = i - (n**2) - n

            Y_mn[i,:] = self.Y(m, n, self.theta, self.phi).reshape(1,-1)

        # reorder channels if Furse-Malham ordering selected
        if self.channel_format == 'FuMa': return self._fuma(Y_mn)
        else: return Y_mn
    
    def Y(self, m, n, theta, phi):
        return (
            self._norm(m, n) * 
            np.array(
                [sp.lpmn(abs(m), n, np.sin(p))[0][abs(m), n] for p in phi]
            ) *
            (np.cos(m * theta) if m >= 0 else np.sin((-m) * theta))
        )
    
    def SN3D(self, m, n):
        delta = lambda m: 1 if m == 0 else 0
        return (
            ((-1)**n) * 
            np.sqrt(
                (2 - delta(m)) * (
                sp.factorial(n - abs(m)) /
                sp.factorial(n + abs(m))
                )
            )
        )
    
    def max_re(self):
        E = max(sp.legendre(self.N+1).r)
        return np.array(
            [
                sp.legendre(
                int(np.sqrt(i)))(E) 
                for i in range(self._n_ambi_channels)
            ]
        )
    
    def _fuma(self, Y_mn):
        if self.N == 1:
            fuma_order = [0, 3, 1, 2]
            Y_mn = Y_mn[fuma_order, :]
        elif self.N == 0:
            warnings.warn('Channel ordering n/a for N = 0')
        else:
            raise ValueError('Cannot use FuMa channel ordering for N > 1')
        return Y_mn