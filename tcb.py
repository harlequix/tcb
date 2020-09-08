"""Tor Snapshot Simulator."""
import argparse
import os
from stem import Flag
from stem.descriptor import parse_file
import logging
from numpy.random import choice
from numpy import array
from restrictions import same_16_subnet, FamilyChecker, build_family_map

logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)


def filter_exits(relays, fast=None, stable=None):
    """Filter tor nodes for exits .

    Parameters
    ----------
    relays : list
        list of tor nodes.
    fast : boolean
        flag if nodes must have fast flag (the default is None).
    stable : type
        flag if nodes must have fast stable (the default is None).

    Returns
    -------
    list
        potential exits.

    """
    ret = [x for x in relays if can_exit(x, fast, stable)]
    logger.debug(f"#{len(ret)} exit nodes found")
    return ret


def filter_middle(relays, fast=None, stable=None):
    """Filter tor nodes for middle nodes.

    Parameters
    ----------
    relays : list
        list of tor nodes.
    fast : boolean
        flag if nodes must have fast flag (the default is None).
    stable : type
        flag if nodes must have fast stable (the default is None).

    Returns
    -------
    list
        potential middle nodes.

    """
    ret = [x for x in relays if can_middle(x, fast, stable)]
    logger.debug(f"#{len(ret)} middle nodes found")
    return ret


def filter_guards(relays, fast=None, stable=None):
    """Filter tornodes for guards.

    Parameters
    ----------
    relays : list
        list of tor nodes.
    fast : boolean
        flag if nodes must have fast flag (the default is None).
    stable : type
        flag if nodes must have fast stable (the default is None).

    Returns
    -------
    list
        potential guards.

    """
    ret = [x for x in relays if can_guard(x, fast, stable)]
    logger.debug(f"#{len(ret)} guard nodes found")
    return ret


def can_exit(relay, fast, stable):
    """Check if a single relay can function as an exit.

    Parameters
    ----------
    relay : relay
        single tor relay.
    fast : boolean
        flag if relay must have fast flag.
    stable : boolean
        flag if relay must have fast stable.

    Returns
    -------
    boolean
        flag if relay can function as an exit .

    """
    return Flag.BADEXIT not in relay.flags and\
        Flag.RUNNING in relay.flags and\
        Flag.VALID in relay.flags and\
        ((not fast) or Flag.FAST in relay.flags) and\
        ((not stable) or Flag.STABLE in relay.flags)


def can_middle(relay, fast, stable):
    """Check if a single relay can function as a middle relay.

    Parameters
    ----------
    relay : relay
        single tor relay.
    fast : boolean
        flag if relay must have fast flag.
    stable : boolean
        flag if relay must have fast stable.

    Returns
    -------
    boolean
        flag if relay can function as a middle relay.

    """
    return \
        Flag.RUNNING in relay.flags and\
        Flag.VALID in relay.flags and\
        ((not fast) or Flag.FAST in relay.flags) and\
        ((not stable) or Flag.STABLE in relay.flags)


def can_guard(relay, fast, stable):
    """Check if a single relay can function as a guard.

    Parameters
    ----------
    relay : relay
        single tor relay.
    fast : boolean
        flag if relay must have fast flag.
    stable : boolean
        flag if relay must have fast stable.

    Returns
    -------
    boolean
        flag if relay can function as a guard

    """
    return \
        Flag.GUARD in relay.flags and\
        Flag.RUNNING in relay.flags and\
        Flag.VALID in relay.flags and\
        ((not fast) or Flag.FAST in relay.flags) and\
        ((not stable) or Flag.STABLE in relay.flags)

def print_num_circuit(circuits):
    print(len(circuits))

def print_circuit(circuits):
    """Print circuits.

    TODO: Move to a callback.py

    Parameters
    ----------
    circuits : list
        list of circuits.

    Returns
    -------
    None

    """
    for guard, middle, exit in circuits:
        print(f"{guard.address} {middle.address} {exit.address}")


def create_circuits(order, guards, middle, exits, weights, restrictions=None, callbacks=None):
    """Create circuits.

    Parameters
    ----------
    order : dict
        dict that contains the information needed for the creation of circuits.
    guards : list
        list of potential guards.
    middle : list
        list of potential middle nodes.
    exits : list
        list of potential exits.
    weights : dict
        dict which contains the weights for every group of nodes.
        # TODO ugly design. Should redo this.
    restrictions : list
        list of callables to filter circuits (should return something) (the default is None).
    callbacks : list
        list of callables to do something with the created circuits (the default is None).

    Returns
    -------
    None

    """
    created = 0
    number = order["number"]
    while created < number:
        if not order["exit"]:
            exit_cand = choice(exits, number-created, p=weights["exits"])
        else:
            exit_cand = order["exit"]
        if not order["middle"]:
            middle_cand = choice(middle, number-created, p=weights["middle"])
        else:
            middle_cand = order["middle"]
        if not order["guard"]:
            guard_cand = choice(guards, number-created, p=weights["guards"])
        else:
            guard_cand = order["guard"]
        circuits = list(zip(guard_cand, middle_cand, exit_cand))
        if restrictions:
            for restriction in restrictions:
                circuits = restriction(circuits)
        if callbacks:
            for cb in callbacks:
                cb(circuits)
        created += len(circuits)
        logger.debug(f"{len(circuits)} circuits created")


def get_bw_weight(flags, position, bw_weights):
    """Return weight to apply to relay's bandwidth for given position.

        flags: list of Flag values for relay from a consensus
        position: position for which to find selection weight,
             one of 'g' for guard, 'm' for middle, and 'e' for exit
        bw_weights: bandwidth_weights from NetworkStatusDocumentV3 consensus

        straight copy from torps
    """
    if (position == 'guard'):
        if (Flag.GUARD in flags) and (Flag.EXIT in flags):
            return bw_weights['Wgd']
        elif (Flag.GUARD in flags):
            return bw_weights['Wgg']
        elif (Flag.EXIT not in flags):
            return bw_weights['Wgm']
        else:
            raise ValueError('Wge weight does not exist.')
    elif (position == 'middle'):
        if (Flag.GUARD in flags) and (Flag.EXIT in flags):
            return bw_weights['Wmd']
        elif (Flag.GUARD in flags):
            return bw_weights['Wmg']
        elif (Flag.EXIT in flags):
            return bw_weights['Wme']
        else:
            return bw_weights['Wmm']
    elif (position == 'exit'):
        if (Flag.GUARD in flags) and (Flag.EXIT in flags):
            return bw_weights['Wed']
        elif (Flag.GUARD in flags):
            return bw_weights['Weg']
        elif (Flag.EXIT in flags):
            return bw_weights['Wee']
        else:
            return bw_weights['Wem']
    else:
        raise ValueError('get_weight does not support position {0}.'.format(
            position))


def assign_weights_by_roles(relays, scale, position, weights):
    """Calculate the weight of relays according to their position.

    Parameters
    ----------
    relays : list
        Description of parameter `relays`.
    scale : type
        Description of parameter `scale`.
    position : type
        Description of parameter `position`.
    weights : type
        Description of parameter `weights`.

    Returns
    -------
    type
        Description of returned object.

    Almost straight copy from torps.

    """
    out = []
    for relay in relays:
        weight = get_bw_weight(relay.flags, position, weights)/scale
        bw = float(relay.bandwidth)
        out.append(bw*weight)
    return out


def create_order(line):
    """Parse a line to extract order for circuit creation.

    Parameters
    ----------
    line : str
        line of order file.

    Returns
    -------
    dict
        dict of the order information.

    """
    line = line.strip("\n")
    fields = ["number", "guard", "middle", "exit", "destination", "extra"]
    order = {i: None for i in fields}
    splitted = line.split(" ", len(fields))
    for field, data in zip(fields[:len(splitted)], splitted):
        order[field] = data
    order["number"] = int(order["number"])  # TODO catch exception
    for field in fields[1:4]:
        if order[field] == "*":
            order[field] = None
    return order


def can_exit_port(exit, policy, destination):
    """Check if relay allows exit to destination.

    Parameters
    ----------
    exit : relay
        tor relay.
    destination : str
        target destionation in form of <ip address>:<port>.

    Returns
    -------
    boolean
        flag if relay allows exit to destination.

    """
    if not destination:
        return True
    port = int(destination.split(":")[1])
    for rule in policy:
        if port >= rule.min_port and port <= rule.max_port:
            if rule.is_address_wildcard() or\
                    rule.get_masked_bits() == 0:
                if rule.is_accept:
                    return True
                else:
                    return False
    return True


def main():
    """Short summary.

    Parameters
    ----------
    order : path
        file which cotains the circuit orders.
    input_file : path
        path to consensus file.
    descriptor : path
        path to descriptor file.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("order", help="path to order file")
    parser.add_argument("consensus", help="path to microdesc consensus file")
    parser.add_argument("microdesc_dir", help="path to folder of microdescriptors")
    args = parser.parse_args()
    try:
        consensus = parse_file(args.consensus, 'network-status-microdesc-consensus-3 1.0', document_handler='DOCUMENT')
    except TypeError:
        print("File {} does not seem to be a valid Tor file")
    for document in consensus:
        nodes = [document.routers[x] for x in document.routers]
        middle = filter_middle(nodes)
        guards = filter_guards(nodes)
        bandwidth_weights = document.bandwidth_weights
        break

    weights = {}
    weights["guards"] = array(assign_weights_by_roles(guards, 10000, "guard", bandwidth_weights))
    weights["guards"] = weights["guards"]/weights["guards"].sum()  # normalize weights
    # weights["middle"] = [1/len(middle) for m in middle]
    weights["middle"] = array(assign_weights_by_roles(middle, 10000, "middle", bandwidth_weights))
    weights["middle"] = weights["middle"]/weights["middle"].sum()

    # collect micro descriptors
    # also, remember the exit policy for each node, as it is stored in the microdesc
    microdescs = []
    exit_policies = dict()
    for node in nodes:
        digest = node.digest.lower()
        microdesc_path = os.path.join(args.microdesc_dir, digest[0], digest[1], digest)

        microdesc = parse_file(microdesc_path, 'microdescriptor 1.0', document_handler='DOCUMENT')
        for document in microdesc:
            microdescs.append(document)
            exit_policies[digest] = document.exit_policy
            break

    family_map = build_family_map(microdescs, consensus)
    same_family = FamilyChecker(family_map)

    with open(args.order) as order_file:
        for line in order_file:
            order = create_order(line)
            exits = filter_exits(nodes)
            logger.debug(f"len of exits before: {len(exits)}")
            exits = [x for x in exits if can_exit_port(x, exit_policies[x.digest.lower()], order["destination"])]
            logger.debug(f"len of exits after: {len(exits)}")
            # weights["exits"] = [1/len(exits) for e in exits]
            weights["exits"] = array(assign_weights_by_roles(exits, 10000, "exit", bandwidth_weights))
            weights["exits"] = weights["exits"]/weights["exits"].sum()
            logger.debug(order)
            logger.debug(len(exits))
            create_circuits(order, guards, middle, exits, weights, callbacks=[print_num_circuit], restrictions=[same_16_subnet, same_family])


if __name__ == '__main__':
    main()
