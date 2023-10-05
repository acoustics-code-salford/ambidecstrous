import random
import unittest
import soundfile as sf
from ambidecstrous.decoders import RawDecoder, UHJDecoder, ACNDecoder
from ambidecstrous.utils import load_mapping


class TestDecoders(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.x, self.fs = sf.read('tests/test_frame.wav')

    def test_raw_decode(self):
        n = random.randint(1, 25)
        decoder = RawDecoder(n)
        self.assertEqual(decoder.decode(self.x).shape[1], n)

    def test_uhj_decode(self):
        decoder = UHJDecoder(2, 'ACN')
        self.assertWarns(Warning, decoder.decode, clip=self.x)
        self.assertEqual(decoder.decode(self.x).shape[1], 2)

    def test_acn_decode(self):
        n = random.randint(1, 3)
        mapping = load_mapping('mappings/octagon.json', 'Octagon')
        decoder = ACNDecoder(2, mapping, n)

        self.assertWarns(Warning, ACNDecoder, 
                         n_output_channels=2,
                         loudspeaker_mapping=mapping,
                         N=n)

        self.assertWarns(Warning, decoder.decode, clip=self.x)

        # make sure decoding matrix is the correct shape
        self.assertEqual(
            decoder.decoding_matrix().shape, ((n+1)**2, len(mapping[0]))
        )
        # check Z channel is zero for all-horizontal plane layout
        self.assertFalse(decoder.decoding_matrix()[2, :].any())

        mapping = load_mapping('mappings/cube.json', 'Cube')
        decoder = ACNDecoder(2, mapping, n)
        # check Z channel now contains values for elevated loudspeakers
        self.assertTrue(decoder.decoding_matrix()[2, :].any())

if __name__ == '__main__':
    unittest.main()