def same_16_subnet(circuits):
    ret = []
    for circuit in circuits:
        guard, middle, exit = circuit
        if not(
            guard.address.split(".", 2) == middle.address.split(".", 2) or
            guard.address.split(".", 2) == exit.address.split(".", 2) or
                middle.address.split(".", 2) == exit.address.split(".", 2)):
            ret.append(circuit)
    return ret


def build_family_map(descriptors):
    family_map = {}
    family_counter = 0
    for desc in descriptors:
        if desc.family:
            digest = desc.digest
            if digest not in family_map.keys():
                family_map[digest] = family_counter
                for member in desc.family:
                    family_map[member[1:]] = family_counter
                family_counter += 1
    return family_map


class FamilyChecker(object):
    """docstring for FamilyChecker."""

    def __init__(self, family_map):
        super(FamilyChecker, self).__init__()
        self.family_map = family_map

    def same_family(self, node_a, node_b):
        return node_a.digest in self.family_map.keys() and\
            node_b.digest in self.family_map.keys() and\
            self.family_map[node_b.digest] == self.family_map[node_a.digest]

    def __call__(self, circuits):
        out = []
        for circuit in circuits:
            guard, middle, exit = circuit
            if not (self.same_family(guard, middle) or
                    self.same_family(middle, exit) or
                    self.same_family(guard, exit)):
                out.append(circuit)
        return out
