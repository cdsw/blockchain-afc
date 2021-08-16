from T4MLTraining import *
from tensorflow.python.keras.models import clone_model, load_model
from copy import deepcopy
from random import randint
from U1IPFS import *
from os import remove as rm

class ClientI:
    def __init__(self, id_, inp_train, out_train, inp_test, out_test):
        self.id_ = id_
        self.inp_train = inp_train
        self.out_train = out_train
        self.inp_test = inp_test
        self.out_test = out_test
        self.deviation = 1
        self.ipfs = IPFS(id_=self.id_)
        self.hash = ''

    def getWeight(self):
        return sum(flatten(self.inp_train.tolist()[0]))
        
    def extract(self):
        return self.inp_train, self.out_train, self.inp_test, self.out_test
    
    def setModel(self, model):
        model_copy = clone_model(model.model)
        #model_copy.build((None, len(self.inp_train[0]), 1))
        model_copy.compile(optimizer='adam', loss='mse')
        model_copy.set_weights(model.model.get_weights())
        model = deepcopy(model)
        model.model = model_copy
        self.model = model
        self.model.setData(self.inp_train, self.out_train)

    def train(self, iter, draw_loss=False):
        ts = time.time()
        self.model.train()
        te = time.time()
        print("Cli# {0}: {1:.2f} sec".format(self.id_, te - ts), end = '; ')
        if draw_loss == True:
            self.model.drawLoss()
        saveloc = './models'
        savename = '{0}-{1:03d}-{2:04d}.mde'.format(self.id_,iter,randint(0,9999))
        self.hash = self.saveModel(saveloc, savename)
        return self.hash

    def extractModel(self):
        return self.model
    
    def predict(self, frame_in, frame_out, verbose_=False):
        predictor = Prediction(self.inp_test,self.out_test,self.model, frame_in, frame_out)
        predictor.predict()
        predictor.summary("",verbose_)
        self.deviation = predictor.in_percent / 100
        return self.deviation

    # location: use ./models/----.mde
    def saveModel(self, loc, nm):
        l = "{0}/{1}".format(loc, nm)
        self.model.model.save(l, save_format='h5')
        hash = self.ipfs.write(loc + nm)
        rm(l)
        return hash
    
    # location: use ./models/----.mde
    def loadModel(self, loc, nm):      
        l = "{0}/{1}".format(loc, nm)
        md = load_model(l)
        self.model.replaceModel(md)

    def importIPFS(self, loc, nm, hash):
        l = "{0}/{1}.mde".format(loc, nm)
        md = self.ipfs.take(hash,l)
        self.loadModel(loc, nm)

class Distributor:
    def __init__(self, dat, company, location, div_company=True, div_location=False, bin_='40T', frame_out=2, ratio=0.8):
        self.dat = dat
        self.company = company
        self.location = location
        self.divide_by_company = div_company
        self.divide_by_location = div_location # NOT YET IMPLEMENTED
        self.clients = []
        
        self.bin_=bin_
        self.frame_out = frame_out
        self.ratio = ratio

    def divByCompany(self):
        for c in self.company:
            tr = DataPrep(self.dat,[c],self.location,[c],self.location,self.bin_,self.frame_out,self.ratio)
            tr.setup()

            inp_train, out_train, inp_test, out_test = tr.extract()
            cli = ClientI(str(c), inp_train, out_train, inp_test, out_test)
            self.clients.append(cli)
    
    def extractClients(self):
        return self.clients

def weighting(model, wei):
    for i in range(len(model)):
        model[i] *= wei
    return model

def combine_models(m1, m2):
    m = deepcopy(m1)
    for i in range(len(m1)):
        m[i] += m2[i]
    return m

class Server:
    def __init__(self, clients, frame_in, frame_out, model_type, epochs_):
        self.id_ = 'S'
        self.clients = clients
        if model_type == 'CNNLSTM':
            self.model = CNNLSTM(frame_in, frame_out, epochs=epochs_)
        self.frame_in = frame_in
        self.frame_out = frame_out
        self.ipfs = IPFS(self.id_)
        self.cli_hashes = []

    def askClients(self, iter):
        for c in self.clients:
            hash = c.train(iter)
            #self.ipfs.take(hash,'./models/temp')
            #c.loadModel('./models','temp')
            self.cli_hashes.append(hash)

    def aggregate(self, mode='amt'): 
        multiplier = []
        cli_weights = []
        # get client demand size and weights
        for h in self.cli_hashes:
            temp_loc = './models/temp'
            self.ipfs.take(hash,temp_loc)
            m = load_model(temp_loc)
            rm(temp_loc)
            cli_sel = None
            for c in self.clients:
                if c.hash == hash:
                    cli_sel = c
                    break
            if mode == 'amt':
                w = cli_sel.getWeight()
            elif mode == 'pre':
                w = cli_sel.predict(self.frame_in, self.frame_out, verbose_=0)
                try:
                    w = (1 / w)
                except ZeroDivisionError:
                    w = 1
            multiplier.append(w)
            cli_weights.append(m.get_weights())
        total_multiplier = sum(multiplier)

        # get proportions
        multiplier_proportion = []
        for w in multiplier:
            multiplier_proportion.append(w/total_multiplier)
        
        # averaging
        average = None
        for i in range(len(cli_weights)):
            weighted = weighting(cli_weights[i],multiplier_proportion[i])
            if average == None:
                average = weighted
            else:
                average = combine_models(average, weighted)

        # repacking in global model
        self.model.model.set_weights(average)
        self.model.model.build((None,self.frame_in,1))
        self.model.model.compile(optimizer='adam',loss='mse')

    def sendGlobalModel(self, loc, iter):
        nm = "{0}-{1:03d}-{2:04d}.mde".format(self.id_, iter, 0)
        # MODEL NEEDS TO BE SAVED INTO A FILE FIRST
        self.model.model.save(loc + '/' + nm, save_format="h5")
        hash = self.ipfs.write(loc + '/' + nm)
        for c in self.clients:
            c.importIPFS(loc, nm, hash)

    def iterate(self, iters, loc, mode='amt'):
        for i in range(iters):
            self.cli_hashes = []
            print("\nIteration " + str(i + 1) + " of " + str(iters), end=' | ')
            tsg = time.time()
            self.sendGlobalModel(loc, i) # loop start
            tsh = time.time()
            self.askClients(i)
            tsi = time.time()
            self.aggregate(mode)
            tsj = time.time()
            print(" | Glob: {0:.2f}s, Train: {1:.2f}s, Aggr: {2:.2f}s.".format(tsh-tsg, tsi-tsh, tsj-tsi))
        return self

