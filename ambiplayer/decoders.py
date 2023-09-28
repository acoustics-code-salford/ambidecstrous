import numpy as np

raw = lambda clip: clip

def stereo_uhj(clip, channel_order='ACN'):

    clip = np.fft.fft(clip.T)

    if channel_order == 'ACN': W, Y, _, X = clip
    elif channel_order == 'FuMa': W, X, Y, _ = clip

    S = 0.9396926*W + 0.1855740*X
    D = 1j * (-0.3420201*W + 0.5098604*X) + 0.6554516*Y

    L = np.fft.ifft(((S + D)/2.0))
    R = np.fft.ifft(((S - D)/2.0))

    L = np.expand_dims(np.real(L), 1)
    R = np.expand_dims(np.real(R), 1)

    return np.concatenate((L, R), 1)