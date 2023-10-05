import math
import warnings
import numpy as np
import scipy.special as sp


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
            N
    ) -> None:
        super().__init__(n_output_channels)
        n_loudspeakers = len(loudspeaker_mapping[0])
        if n_output_channels < n_loudspeakers:
            warnings.warn('Fewer output channels on device ' +
                          f'({n_output_channels}) than specified ' +
                          f'in loudspeaker mapping ({n_loudspeakers}). ' + 
                          'Output will be truncated to available channels.')

        self.N = N
        self.loudspeaker_mapping = loudspeaker_mapping
    
    @property
    def N(self):
        return self._N
    
    @N.setter
    def N(self, N):
        self._N = N
        self._n_ambi_channels = (N+1) ** 2

    @property
    def loudspeaker_mapping(self):
        return [self.channels, self._theta, self._phi]
    
    @loudspeaker_mapping.setter
    def loudspeaker_mapping(self, mapping):
        self.channels, self._theta, self._phi = mapping
    
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
        clip = self._w() * clip @ self.decoding_matrix() 
        # passing through super makes sure output channel count is correct
        return super().decode(clip)

    def decoding_matrix(self):
        Y_mn = np.zeros([(self.N+1)**2, len(self._theta)])
        for i in range((self.N+1)**2):
            # trick from ambiX paper
            n = math.isqrt(i)
            m = i - (n**2) - n
            Y_mn[i,:] = self.Y(m, n).reshape(1,-1)
        return Y_mn
    
    def Y(self, m, n):
        return (
            ((-1) ** m) * # condon-shortley compensation
            self._norm(m, n) * 
            np.array(
                [sp.lpmn(abs(m), n, np.sin(p))[0][abs(m), n] for p in self._phi]
            ) *
            (np.cos(m * self._theta) if m >= 0 else np.sin((-m) * self._theta))
        )
    

class ACNDecoder(AmbisonicDecoder):
    def __init__(self, n_output_channels, loudspeaker_mapping, N) -> None:
        self._w = self._max_re
        self._norm = self._SN3D
        super().__init__(n_output_channels, loudspeaker_mapping, N)

    def _SN3D(self, m, n):
        delta = lambda m: 1 if m == 0 else 0
        return (
            np.sqrt(
                (2 - delta(m)) * (
                sp.factorial(n - abs(m)) /
                sp.factorial(n + abs(m))
                )
            )
        )
    
    def _max_re(self):
        E = max(sp.legendre(self.N+1).r)
        return np.array(
            [
                sp.legendre(
                int(np.sqrt(i)))(E) 
                for i in range(self._n_ambi_channels)
            ]
        )
    
    # def _fuma(self, Y_mn):
    #     if self.N == 1:
    #         fuma_order = [0, 3, 1, 2]
    #         Y_mn = Y_mn[fuma_order, :]
    #     elif self.N == 0:
    #         warnings.warn('Channel ordering n/a for N = 0')
    #     else:
    #         raise ValueError('Cannot use FuMa channel ordering for N > 1')
    #     return Y_mn
