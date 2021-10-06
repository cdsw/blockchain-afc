from T10FLWIPFS import weighting, combine_models, os, load_model
from T4MLTraining import *
from U2IPFS import *

from math import log
from random import randint
from copy import deepcopy
import time

os.chdir("/home/cl/Documents/n-bafc/blockchain-afc/taxi")
print(os.getcwd())

settings = {
    'frame_in' : 36,
    'frame_out' : 2,
    'ratio' : 0.8,
    'bin' : '40T'}

class Distributor:
    def __init__(self, dat, company, location, settings_):
        self.dat = dat
        self.company = company
        self.location = location
        self.clients = []
        
        self.bin_=settings_['bin']
        self.frame_out = settings_['frame_out']
        self.ratio = settings_['ratio']

    def divBoth(self, settings):
        for c in self.company:
            for l in self.location:
                tr = DataPrep(self.dat,[c],[l],[c],[l],self.bin_,self.frame_out,self.ratio)
                tr.setup()

                inp_train, out_train, inp_test, out_test = tr.extract()
                if (c, l) == (3,4) or (c,l) == (5,4):
                    cli = Miner(str(c) + '/' + str(l), settings)
                else:
                    cli = Client(str(c) + '/' + str(l), settings)
                cli.setData(inp_train, out_train, inp_test, out_test)
                self.clients.append(cli)
                
    def extractClients(self):
        return self.clients

class Transaction:
    def __init__ (self, chain, sender, recipient, load, type_, payment): #type_ - model/pay
        self.sender = sender
        self.load = load
        self.recipient = recipient
        self.type = type_
        self.payment = payment
        self.chain = chain
    
    def __str__(self):
        r = "TRX: C{0:5.5}:{1:5.5}-->{2:5.5} | {3:5.5} | ¤{4:4d} | Hashes: ".format(self.chain, self.sender, self.recipient, self.type, self.payment) + self.load
        return r

class Block:
    def __init__(self, chain, chain_idx, trxs, proof, prev_hash, ts=None, repu_list=None):
        self.chain = chain
        self.chain_idx = chain_idx
        self.transactions = trxs
        self.proof = proof
        self.prev_hash = prev_hash
        if ts == None:
            self.timestamp = time.time()
        else:
            self.timestamp = ts
        if repu_list == None:
            self.reputation_list = {}
        else:
            self.reputation_list = repu_list

    def __str__(self):
        r = "BLK: C:{0:7.7}#{1:3d} <-- PH={2:5.5}:PF={3:5.5}, RL={4:5.5}, #TRXS={5}".format(str(self.chain.bc_id),self.chain_idx,str(self.prev_hash),str(self.proof),str(self.reputation_list), str(len(self.transactions)))
        return r

# =================================================================================================
def removeCli(txns, cli): #in dict
    for k in range(len(txns)):
        if txns[k].type == 'MOD' and txns[k].sender == cli:
            txns.remove(txns[k])
    return txns

def truncateViewRL(rl):
    r = ""
    for c, q in rl.items():
        r += "{0:5.5}:{1:.4}; ".format(c,q)
    return r
# ==============================================================================================================
class Client:
    def __init__(self, alias, settings):
        self.alias = alias
        self.id = str(hash(alias + str(randint(3,418000))))
        self.ipfs = IPFSN(alias)
        self.blockchain = None
        self.balance = 0

        #settings
        self.frame_in = settings['frame_in']
        self.frame_out = settings['frame_out']
        self.ratio = settings['ratio']
        self.bin = settings['bin'] 
        self.epoch = 1 #-------------------------------------------------- 110/3

        #pre-assignment placeholder
        self.inp_train = None
        self.out_train = None
        self.inp_test = None
        self.out_test = None

    def __str__(self):
        r = "{0}:{3}-{1:5.5}, {2:7d}".format(self.getType(), self.id, self.getMultiplier(), self.alias)
        return r

    def getType(self):
        return "CLI"

    def getMultiplier(self):
        return sum(flatten(self.inp_train.tolist()[0]))

    def assignBlockchain(self, blockchain):
        self.blockchain = blockchain
        self.bc_id_raw = id(blockchain)
        self.bc_id = str(hex(self.bc_id_raw))

    def importChain(self, blockchain): # chain: type Blockchain
        self.blockchain = deepcopy(blockchain)
        last_block = blockchain.lastBlock()
        #get transactions
        trx = last_block.transactions
        aggr = self.aggregate(trx)
        self.replaceWeights(aggr)
                        
    def aggregate(self, trxs):
        weights = []
        multiplier = []
        total_multiplier = 0
        multiplier_proportion = []
        loc = "./models/"
        for t in trxs:
            weightHash, multiplierHash = t.split('|')[0], t.split('|')[1]
            #import weights and multiplies from IPFS
            self.ipfs.fetch(weightHash,loc + weightHash)
            self.ipfs.fetch(multiplierHash,loc + multiplierHash)
            # read model
            md = load_model(self.loc+weightHash).get_weights()
            weights.append(md)
            # read multiplier
            f = open(loc + multiplierHash, "r")
            mult = int(f.read())
            total_multiplier += mult
            multiplier.append(mult)
            os.remove(self.loc+weightHash)
            os.remove(self.loc+multiplierHash)

        # get proportions
        for w in multiplier:
            multiplier_proportion.append(w/total_multiplier)

        # averaging
        average = None
        for i in range(len(weights)):
            weighted = weighting(weights[i],multiplier_proportion[i])
            if average == None:
                average = weighted
            else:
                average = combine_models(average, weighted)
        return average

    def replaceWeights(self, weights):
        self.model.model.set_weights(weights)
        self.model.model.build((None,self,self.frame_in,1))
        self.model.model.compile(optimizer='adam',loss='mse')

    def setData(self, inp_train, out_train, inp_test, out_test):
        self.inp_train = inp_train
        self.out_train = out_train
        self.inp_test = inp_test
        self.out_test = out_test
        self.multiplier = self.getMultiplier()

    def train(self):
        # DONE AFTER AGGREGATION
        loc='./models/temp{0}.h5'.format(self.id)
        ts = time.time()
        self.model.train(epochs_=self.epoch)
        te = time.time()
        print("#{0}:{1:.2f}s".format(self.alias, te - ts), end = '; ')
        # save model to file
        self.model.model.save(loc, save_format='h5')
        # save to IPFS
        self.hash = self.ipfs.submit(loc)
        locM ='./models/temp{0}.fil'.format(self.id)
        f = open(locM, 'w')
        f.write(str(self.getMultiplier()))
        f.close()
        self.hashM = self.ipfs.submit(locM)
        os.remove(loc)
        os.remove(locM)

    def submitModelAsTransaction(self):
        # send model HASH and MULTIPLIER (number of data)
        load = self.hash + '|' + self.hashM
        trx = Transaction(self.bc_id_raw, self.id, 0, load, 'MOD', 0)
        chidx = self.blockchain.newTransaction(trx)
        print("{0}:{1} MOD-->CHIDX#{2:3d}".format(self.getType(),self.alias, chidx))

# ============================================================================================
class Miner(Client):
    def __init__(self, alias, settings):
        super().__init__(alias, settings)

    def getType(self):
        return "MIN"

    def incentivize(self, ): ######## LAYER 2 INCENTIVE #OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
        load = 'Incentive to Node ' + recipient
        trx = Transaction(self.bc_id_raw, self.id, recipient, load, "PAY", payment)
        # |||||||||||||||||||||||||||||||||||| ADD TO TRX
    
    def mine(self): # RETURN BLOCK
        print("Start mining: " + self.alias)
        
        # GET TRANSACTIONS
        self.last_trxs = deepcopy(self.blockchain.current_transactions)

        t_hashes = [] #fill with (id, hash, hashM)
        for t in self.last_trxs:
            if t.type == 'MOD':
                t_hashes.append((t.sender,t.load,None))
        
        # PoA
        if self.blockchain.proofOfAuthority(self.id) == False:
            return

        loc = "./models/"
        t_creds = []
        # Obtain quality
        for t in t_hashes:
            t_mod, t_amt = t[1].split('|')
            t_id = t[0]
            # download
            self.ipfs.fetch(t_mod,loc)
            self.ipfs.fetch(t_amt,loc)
            # open files
            fH = open(loc + t_amt, "r")
            mul = fH.read()
            fH.close()
            md = load_model(loc+t_mod).get_weights()
            t_creds.append((t_id, md, mul))
            os.remove(loc+t_mod)
            os.remove(loc+t_amt)

        bogus_model = CNNLSTM(self.frame_in, self.frame_out)
        bogus_model.model.compile(optimizer='adam',loss='mse')         
        
        rl_current = {}
        for t in range(len(t_creds)):
            t_id, t_mod, t_mul = t_creds[t][0], t_creds[t][1], int(t_creds[t][2])
            bogus_model.model.set_weights(t_mod)
            bogus_model.model.build((None,self.frame_in,1))
            bogus_model.model.compile(optimizer='adam',loss='mse')         
            # prediction phase
            dev = self.predict(bogus_model)
            # quality calculation
            qual = dev * (1 + log(t_mul, 1000)) * (1 + log(self.getMultiplier()), 1000)
            rl_current[t_id] = qual[0]

        resp = ""
        for ci, qu in rl_current.items():
            resp += "{0}|{1};".format(ci,qu)

        # send qual to IPFS and attach to proposed block
        f = open(loc+'tempQ','w')
        f.write(resp)
        f.close()
        hashQ = self.ipfs.submit(loc+'tempQ')
        os.remove(loc+'tempQ')
        # PoQ
        self.blockchain.proofOfQuality(self.id, hashQ)
        return

    def distributePayment(self):
        # distribute payments into clients for each trx (???)


        # last: clear last trxs
        self.last_trxs = []

    def predict(self, model, verbose_=False):
        predictor = Prediction(self.inp_test,self.out_test,model,self.frame_in, self.frame_out)
        predictor.predict()
        predictor.summary("",verbose_)
        self.deviation = predictor.in_percent / 100
        return self.deviation

# ==================================================================================================

class Blockchain(object): # PROVING NODE: ID + SALT + HASH
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.bc_id = str(hex(id(self)))
        self.block_backlog = []
        self.clients = set()
        self.cli_pointers = []
        self.newBlock(previous_hash=0, proofA=0, proofQ=0, trxs=[]) # CHANGE PREV HASH AND PROOF ???
        self.salt = str(randint(1,100000)) # salt for this blockchain
        print("Blockchain created with ID: " + self.bc_id + " " + str(int(self.bc_id,base=16)))
        self.ipfs = IPFSN(self.bc_id)
        self.latest_repu_inc = {}

    def authorizeClient(self, client):
        # hash is secret to the
        cid_hash = hash(client.id + self.salt)
        self.clients.add(cid_hash)
        self.cli_pointers.append(client)

    def proofOfAuthority(self, clientId):
        if hash(clientId + self.salt) not in self.clients:
            print("{0:5.5} MINE REJECTED: UNAUTH".format(clientId))
            return False
        print("{0:5.5} MINE APPROVED: POA".format(clientId))
        return True

    def proofOfQuality(self, clientId, hashQ):
        # get prev stuff and see diffs
        rl_prev = self.lastBlock.reputation_list

        loc = './models/'

        # load hashQ
        self.ipfs.fetch(hashQ, loc)
        f = open(loc + hashQ, 'r')
        rl_current = f.read()
        f.close()
        os.remove(loc + hashQ)

        if type(rl_prev) == str:
            self.ipfs.fetch(rl_prev, loc)
            f = open(loc + rl_prev, 'r')
            rl_pre = f.read()
            f.close()
            os.remove(loc + rl_prev)
     
            rl_prev = {}
            rl_clis = rl_pre.split(';')[:-1]
            for l in rl_clis:
                k = l.split('|')
                rl_prev[k[0]] = float(k[1])

        dc_rl = {}
        rl_clis = rl_current.split(';')[:-1]
        for l in rl_clis:
            k = l.split('|')
            dc_rl[k[0]] = float(k[1])

        trxs = deepcopy(self.current_transactions)
        # Update values

        updated = {}
        for cli, qual in dc_rl.items():
            if cli not in rl_prev.keys():
                updated[cli] = qual
            elif updated[cli] < qual:
                updated[cli] = qual
            else:
                trxs = removeCli(trxs, cli)

        print("PREV="+truncateViewRL(rl_prev)+ " CURR="+truncateViewRL(updated))

        if len(trxs) == 0:
            print("{0:5.5} MINE REJECTED: SUBSTANDARD".format(clientId))
            return False

        print("{0:5.5} MINE APPROVED AND ACCEPTED: POQ".format(clientId))
        #print(block)
        self.newBlock(clientId, hashQ, trxs)
        return True

    def newBlock(self, proofA, proofQ, trxs, previous_hash=None, mode="MINE", incentive_list=None): # int str |> dict
        if previous_hash == None:
            previous_hash = str(hash(self.chain[-1]))
        try:
            block = Block(self,self.lastBlock.chain_idx + 1,
                            trxs, proofA, 
                            self.lastBlock.prev_hash, 
                            repu_list=proofQ)
        except Exception as e:
            print(e, end='|')
            print("Brand new blockchain, creating genesis block")
            block = Block(self,0,[], proofA, proofQ, repu_list={})
            self.chain.append(block)

        if mode == "MINE":
            print(block)
            # ADD TO BACKLOG
            self.block_backlog.append(block)
        elif mode == "CONSENSUS":
            self.incentivize(incentive_list)
            for tx in trxs:
                if tx.type == "PAY":
                    for ci in self.cli_pointers:
                        if tx.sender == ci.id:
                            ci.balance -= tx.payment
                        if tx.recipient == ci.id:
                            ci.balance += tx.payment
                    print("TRX: {0:5.5} > [{1:4.2d}] > {1:5.5}".format(tx.sender, tx.payment, tx.recipient))
            self.chain.append(block)
        return block

    def newTransaction(self, trx):
        self.current_transactions.append(trx)
        return self.lastBlock.chain_idx + 1

    @property
    def lastBlock(self):
        return self.chain[-1]
        
    def consensus(self):
        loc = "./models/"
        cl_rl = {}
        for blk in self.block_backlog:
            cl, rl = blk.proof, blk.reputation_list
            try:
                self.ipfs.fetch(rl,loc)
                f = open(loc + rl, 'r')
                rle = f.read()
                f.close()
                os.remove(loc+rl)

                rl = {}
                rl_clis = rle.split(';')[:-1]
                for l in rl_clis:
                    k = l.split('|')
                    rl[k[0]] = float(k[1])

                cl_rl[cl] = rl
            except Exception as e:
                pass
                #print(e)
        
        res = {}
        
        # Get max
        for k, r in cl_rl.items():
            if len(res) == 0:
                for k, v in r.items():
                    res[k] = v
            else:
                for k, v in r.items():
                    if r[k] > res[k]:
                        res[k] = r[k]

        rl_prev = self.lastBlock.reputation_list
        if type(rl_prev) == str:
            self.ipfs.fetch(rl_prev, loc)
            f = open(loc + rl_prev, 'r')
            rl_pre = f.read()
            f.close()
            os.remove(loc + rl_prev)

            rl_prev = {}
            rl_clis = rl_pre.split(';')[:-1]
            for l in rl_clis:
                k = l.split('|')
                rl_prev[k[0]] = float(k[1])

        c_inc = {}
        rl_deviation = {}
        
        print(rl_prev)
        # Give credit
        for cli, rli in cl_rl.items():
            c_inc[cli] = 0
            for k, v in rli.items():
                if rli[k] == res[k]:
                    try:
                        rl_deviation[rli[k]]
                        c_inc[cli] += rli[k] - rl_prev[k]
                    except KeyError:
                        if c_inc[cli] != 0:
                            c_inc[cli] += rli[k]
                        else:
                            c_inc[cli] = rli[k]
                
        proofA = ""
        for cli in c_inc.keys():
            if c_inc[cli] > 0:
                proofA += str(cli) + "|"
        
        loc_ = "./models/tempD"
        f = open(loc_, "w")
        f.write(str(cl_rl))
        f.close()
        proofQ = self.ipfs.submit(loc_)
        os.remove(loc_)

        block = self.newBlock(proofA, proofQ, self.current_transactions, mode="CONSENSUS", incentive_list=c_inc)
        print(block, " -- CONSENSUS")
        return c_inc

    def incentivize(self, inc):
        # SEPARATE TRX AND MODEL TRX
        for c, i in inc.items():
            for cl in self.cli_pointers:
                if cl.id == c and i != 0:
                    tx = Transaction(self.bc_id,0,cl.id,'incentivization',"PAY",i)
                    self.newTransaction(tx)
                    cl.incentivize() #OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
            inc[c] = 0