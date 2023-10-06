import json
import numpy as np


def load_mapping(mapping_file, name):
    with open(mapping_file, 'r') as file:
        mapping = json.load(file)[name]
        channel_numbers = [int(key) for key in mapping.keys()]
        theta = np.radians(
            [float(x['azimuth']) for x in mapping.values()]
        )
        phi = np.radians(
            [float(x['elevation']) for x in mapping.values()]
        )
        return [channel_numbers, theta, phi]
