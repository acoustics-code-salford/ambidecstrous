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

        if self.channel_format == 'ACN':
            W, Y, _, X = clip
        elif self.channel_format == 'FuMa':
            W, X, Y, _ = clip

        S = 0.9396926*W + 0.1855740*X
        D = 1j * (-0.3420201*W + 0.5098604*X) + 0.6554516*Y

        L = np.fft.ifft(((S + D)/2.0))
        R = np.fft.ifft(((S - D)/2.0))

        L = np.expand_dims(np.real(L), 1)
        R = np.expand_dims(np.real(R), 1)

        clip = np.concatenate((L, R), 1)

        # passing through super makes sure output channel count is correct
        return super().decode(clip)


class ACNDecoder(RawDecoder):
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
        clip = clip @ self.decoding_matrix()
        # passing through super makes sure output channel count is correct
        return super().decode(clip)

    def decoding_matrix(self):
        return np.array([
            self._y_vector_real(t, f) 
            for (t, f) in zip(self._theta, self._phi)
        ]).T

    def _acn_index(self, n, m):
        return n**2 + n + m

    def _y_vector_real(self, theta, phi):
        """Compute real-valued ACN/SN3D spherical harmonic vector."""
        Y = np.zeros(((self.N+1)**2,), dtype=float)
        for n in range(self.N+1):
            for m in range(-n, n+1):
                Y[self._acn_index(n, m)] = self.sn3d_real_y(n, m, theta, phi)
        return Y

    def sn3d_real_y(self, n, m, theta, phi):
        """Real SN3D spherical harmonic (ACN ordering)."""
        Y = sp.sph_harm_y(n, abs(m), theta, phi)
        K = np.sqrt((2 - int(m == 0)) * 
                    math.factorial(n - abs(m)) / 
                    math.factorial(n + abs(m)))
        if m < 0:
            return np.sqrt(2) * (-1)**m * Y.imag * K
        elif m == 0:
            return Y.real * K
        else:  # m > 0
            return np.sqrt(2) * (-1)**m * Y.real * K


    # def _max_re(self):
    #     E = max(sp.legendre(self.N+1).r)
    #     return np.array(
    #         [
    #             sp.legendre(int(np.sqrt(i)))(E)
    #             for i in range(self._n_ambi_channels)
    #         ]
    #     )
