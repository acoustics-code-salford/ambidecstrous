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
            weighting='flat'
    ) -> None:
        super().__init__(n_output_channels)
        n_loudspeakers = len(loudspeaker_mapping[0])
        if n_output_channels < n_loudspeakers:
            warnings.warn('Fewer output channels on device ' +
                          f'({n_output_channels}) than specified ' +
                          f'in loudspeaker mapping ({n_loudspeakers}). ' + 
                          'Output will be truncated to available channels.')

        self.N = N
        self.channel_format = channel_format
        self.loudspeaker_mapping = loudspeaker_mapping
        self.normalisation = normalisation
        self.weighting = weighting

    @property
    def N(self):
        return self._N
    
    @N.setter
    def N(self, N):
        self._N = N
        self._n_ambi_channels = (N+1)**2
        print(self._n_ambi_channels)
        try: self.loudspeaker_mapping
        except AttributeError: pass
        else:
            print(self.decoding_matrix().shape)
            print(self.decoding_matrix())

    @property
    def loudspeaker_mapping(self):
        return [self.channels, self.theta, self.phi]
    
    @loudspeaker_mapping.setter
    def loudspeaker_mapping(self, mapping):
        self.channels, self.theta, self.phi = mapping

        # transfer angles to correct ranges for scipy.sph_harm
        # e.g. theta in [0, 2*pi], phi in [0, pi]
        theta_map = lambda theta: (- theta + (2*np.pi)) % (2*np.pi)
        phi_map = lambda phi: (- phi - np.pi/2) % np.pi
        self.theta = theta_map(self.theta)
        self.phi = phi_map(self.phi)

        print(self.decoding_matrix().shape)
        print(self.decoding_matrix())

    
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
        Y_mn = np.zeros([len(self.theta), (self.N+1)**2], dtype=complex)

        for i in range((self.N+1)**2):
            # trick from ambiX paper
            n = np.floor(np.sqrt(i))
            m = i - (n**2) - n
            Y_mn[:,i] = sp.sph_harm(m, n, self.theta, self.phi).reshape(1,-1)

        # convert complex to real SHs
        Y_mn = np.real(self.C() @ Y_mn.T).T

        # reorder channels if Furse-Malham ordering selected
        if self.channel_format == 'FuMa':
            if self.N == 1:
                fuma_order = [0, 3, 1, 2]
                Y_mn = Y_mn[:, fuma_order]
            elif self.N == 0:
                warnings.warn('Channel ordering n/a for N = 0')
            else:
                raise ValueError('Cannot use FuMa channel ordering for N > 1')
            
        return np.linalg.pinv(Y_mn)
    

    def C(self):
        C = []
        for n in range(self.N+1): C.append(self.c(n))
        return block_diag(*[x for x in C])


    def c(self, n): # complex/real transform matrix
        indices = self.rotation_indices(n)
        C = np.zeros((2*n+1)**2, dtype=complex)

        for i, (_, m, mp) in enumerate(indices):
            if abs(m) != abs(mp):
                C[i]  = 0
            elif m - mp == 0: # same sign
                if m == 0: # both 0
                    C[i] = np.sqrt(2)
                elif m < 0: # both negative
                    C[i] = 1j
                else: # both positive
                    C[i] = (int(-1)**int(m))
            elif m - mp > 0: # mp negative
                C[i] = 1
            elif m - mp < 0: # mp positive
                C[i] = -1j*(int(-1)**int(m))

        C *= 1/(np.sqrt(2))
        return C.reshape(2*n+1, 2*n+1)
    

    def rotation_indices(self, n):
        return np.array(
            [
                [n,m,mp] for n in range(n,n+1)
                for m in range(-n, n+1) for mp in range(-n, n+1)
            ]
        )