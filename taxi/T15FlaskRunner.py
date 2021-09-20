from T14BFLCore import *
import _ctypes
port_ = 5002

blockchain = Blockchain(url="http://0.0.0.0:" + str(port_) + "/")
print_(id(blockchain))
print(int(blockchain.bc_id, base=16))

# save bc id to file
f = open("./models/chaincred", 'w')
f.write(str(int(blockchain.bc_id, base=16)))
f.close()

app = Flask(__name__)
node_identifier = "0"

@app.route('/')
def index():
    return "<p>Test Page</p>"

@app.route('/mine', methods=['POST'])
def mine():
    # MINE should be POST???
    m = request.get_json(force=True)
    block_ = toBlock(m)

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

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    # notify clients : notify()
    
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def newTransaction():
    values = request.get_json(force=True)
    # Create a new Transaction
    index = blockchain.newTransaction(values['sender'], values['recipient'], values['load'],values['type'], values['payment'])
    print_(blockchain.current_transactions)
    print_(blockchain.bc_id)
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def fullChain():
    response = "NOT IMPLEMENTED"
    #response = {'chain': blockchain.chain, 'length': len(blockchain.chain)}
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def registerNodes():
    values = request.get_json(force=True)
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.authorizeClient(node)
    response = {'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),}
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    response = "NOT IMPLEMENTED"
    #replaced = blockchain.resolveConflicts()
    #if replaced:
    #    response = {'message': 'Our chain was replaced',
    #        'new_chain': blockchain.chain}
    #else:
    #    response = {'message': 'Our chain is authoritative',
    #        'chain': blockchain.chain}
    return jsonify(response), 200

app.run(host='0.0.0.0', port=port_)