import ipfshttpclient as ip
import os

class IPFS:
    def __init__(self, id_):
        self.id_ = id_
        self.cli = ip.connect()
        self.id = self.cli.id()['ID']
    
    # dat: binary or model file
    def write(self, dat):
        dirname = os.path.dirname(__file__)
        d = self.cli.add(dirname + '/' + dat)
        hash = d['Hash']
        return hash
    
    def returnURL(self, idx):
        port = 3333
        url = 'http://localhost:{0:d}/ipfs/{1}'.format(port,self.lstdata[idx])
        return url

    # loc: folder. Use ./models
    def take(self, hash, loc):
        self.cli.get(hash, loc)

    def close(self):
        self.cli.close()

    # https://stackoverflow.com/questions/43118022/how-do-i-unpin-and-remove-all-ipfs-content-from-my-machine