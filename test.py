import os
import argparse
import torch
import numpy as np
from torch.utils.data import DataLoader
from lib.build.registry import Registries
from lib.datasets.cifar import *
from lib.models.backbones.resnet import *
import tqdm
import pandas as pd
from torch.nn import functional as F
from torch.utils.tensorboard import SummaryWriter
from lib.utils.saver import Saver
from lib.utils.logger import Logger
from lib.utils.evaluator import Evaluator
from lib.utils import transforms
from lib.utils.loss import FocalLoss
class Tester:
        def __init__(self,args):
                self.args=args         

                # Define Saver
                self.saver = Saver(args)

                # Define Evaluator
                self.evaluator = Evaluator(args.num_classes)

                # Define SummaryWriter
                self.writer = SummaryWriter()

                # Define Dataloader
                kwargs = {'num_workers': args.num_workers, 
                        'pin_memory': True}
                test_transform=transforms.Compose([
                transforms.ToTensor(),
                ])
                test_dataset = Registries.dataset_registry.__getitem__(args.dataset)(args.dataset_path,'test',test_transform) 
                self.test_loader = DataLoader(dataset=test_dataset, batch_size=1, shuffle=True,  **kwargs)

                # Define Model
                self.model = Registries.backbone_registry.__getitem__(args.backbone)(num_classes=10)
                
                # Use cuda
                if torch.cuda.is_available() and args.use_gpu:
                        self.device = torch.device("cuda",args.gpu_ids[0])
                        if len(args.gpu_ids) > 1:
                                self.model = torch.nn.DataParallel(self.model, device_ids=args.gpu_ids)     
                else:
                        self.device = torch.device("cpu")
                self.model = self.model.to(self.device)
                
                # Use pretrained model
                if args.pretrained_model_path is not None:
                        if not os.path.isfile(args.pretrained_model_path):
                                raise RuntimeError("=> no checkpoint found at '{}'" .format(args.pretrained_model_path))
                        else:                      
                                checkpoint = torch.load(args.pretrained_model_path)
                                if args.use_gpu and len(args.gpu_ids) > 1:
                                        self.model.module.load_state_dict(checkpoint['model'])
                                else:
                                        self.model.load_state_dict(checkpoint['model'])
                                print("=> loaded checkpoint '{}' (epoch {})".format(args.pretrained_model_path, checkpoint['epoch']))
                else:
                    raise RuntimeError('No pretrained model!')

        def test(self):                                       
                tbar = tqdm.tqdm(self.test_loader)
                self.model.eval()   #change the model to eval mode
                with torch.no_grad():
                        for step,sample in enumerate(tbar):
                                inputs,labels = sample['data'],sample['label']      #get the inputs and labels from dataloader     
                                inputs,labels = inputs.to(self.device),labels.to(self.device)                    
                                outputs = self.model(inputs)   #get the output(forward)              
                                predicts= torch.argmax(outputs,dim=1)
                                self.evaluator.add_batch(labels.cpu().numpy(),predicts.cpu().numpy())  
                confuse_matrix=self.evaluator.confusion_matrix      
                print('confuse_matrix:',confuse_matrix)
                confuse_matrix_frame=pd.DataFrame(confuse_matrix)
                confuse_matrix_frame.to_csv("confuse_matrix.csv")
                mIOU=self.evaluator.Mean_Intersection_over_Union()
                print('mIOU:',mIOU)

def main():
        # basic parameters
        parser = argparse.ArgumentParser()
        parser.add_argument('--dataset', type=str, default='CIFAR10', help='Dataset you are using.')
        parser.add_argument('--backbone', type=str, default='resnet18', help='Backbone you are using.')
        parser.add_argument('--model', type=str, default='resnet18', help='Model you are using.')
        parser.add_argument('--crop_height', type=int, default=32, help='Height of cropped/resized input image to network')
        parser.add_argument('--crop_width', type=int, default=32, help='Width of cropped/resized input image to network')
        parser.add_argument('--dataset_path', type=str, default='/path/to/test_data',help='path of test data')
        parser.add_argument('--pretrained_model_path', type=str, default='/path/to/pretrained_model',help='path of pretrained model')
        parser.add_argument('--num_workers', type=int, default=4, help='num of workers')
        parser.add_argument('--num_classes', type=int, default=10, help='num of object classes (with void)')
        parser.add_argument('--gpu_ids', type=str, default='0', help='GPU ids used for testing')
        parser.add_argument('--use_gpu', type=bool, default=True, help='whether to user gpu for testing')
        parser.add_argument('--save_path', type=str, default=os.getcwd(), help='path to save results')
        args = parser.parse_args()
        if args.use_gpu:
                try:
                        args.gpu_ids = [int(s) for s in args.gpu_ids.split(',')]
                except ValueError:
                        raise ValueError('Argument --gpu_ids must be a comma-separated list of integers only')

        # start to test
        print(args)
        tester = Tester(args)
        tester.test()
if __name__ == '__main__':
    main()