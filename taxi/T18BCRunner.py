from T17BFLSimpCore import *

blockchain = Blockchain()
print(id(blockchain))
print(int(blockchain.bc_id, base=16))


def mine(block_):
    # check PoA
    if blockchain.proofOfAuthority(block_['sender']) == 0:
        return "Error: unknown node.", 400

    # check PoQ
    quality = blockchain.proofOfQuality(block_)
    if quality == 0:
        return "Not mined: Substandard quality.", 400

    # Success: PoA, PoQ
    # Incentive
    blockchain.newTransaction("0", block_["sender"],'Incentive','payment', int(quality))

    # Forge the new Block by adding it to the chain
    previous_hash = str(hash(blockchain.lastBlock()))
    block = blockchain.newBlock(0, previous_hash) # PROOF LATER_-----------------------------------------------------------------


def newTransaction(trx):
    values = trx #|||||||||||||||||||||||||||||||||||||||||||||||||\
    index = blockchain.newTransaction(values['sender'], values['recipient'], values['load'],values['type'], values['payment'])
    print(blockchain.current_transactions)
    print(blockchain.bc_id)
    response = {'message': f'Transaction will be added to Block {index}'}
    return response

def fullChain():
    pass

def registerNodes(nodes):
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.authorizeClient(node)
    response = {'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),}
    return response

def consensus():
    response = "NOT IMPLEMENTED"
    #replaced = blockchain.resolveConflicts()
    #if replaced:
    #    response = {'message': 'Our chain was replaced',
    #        'new_chain': blockchain.chain}
    #else:
    #    response = {'message': 'Our chain is authoritative',
    #        'chain': blockchain.chain}
    return response