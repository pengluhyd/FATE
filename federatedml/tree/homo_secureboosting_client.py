from federatedml.feature.binning.quantile_binning import QuantileBinning
from federatedml.feature.fate_element_type import NoneType
from federatedml.param.feature_binning_param import FeatureBinningParam
from federatedml.tree import BoostingTree
from federatedml.transfer_variable.transfer_class.homo_secure_boost_transfer_variable import \
    HomoSecureBoostingTreeTransferVariable
from federatedml.transfer_variable.transfer_class.homo_decision_tree_transfer_variable import \
    HomoDecisionTreeTransferVariable
from federatedml.tree.homo_secureboosting_aggregator import SecureBoostClientAggregator
from federatedml.util import consts
from federatedml.loss import SigmoidBinaryCrossEntropyLoss
from federatedml.loss import SoftmaxCrossEntropyLoss
from federatedml.loss import LeastSquaredErrorLoss
from federatedml.loss import HuberLoss
from federatedml.loss import LeastAbsoluteErrorLoss
from federatedml.loss import TweedieLoss
from federatedml.loss import LogCoshLoss
from federatedml.loss import FairLoss
from federatedml.tree.homo_decision_tree_client import HomoDecisionTreeClient
from federatedml.feature.instance import Instance
from federatedml.feature.sparse_vector import SparseVector

import functools
from numpy import random

from typing import List, Tuple, Dict
from arch.api.table.eggroll.table_impl import DTable
import numpy as np
from arch.api.utils import log_utils

LOGGER = log_utils.getLogger()

class LocalTestLogger(object):

    def __init__(self):
        pass

    def debug(self, *args):
        print(*args)

    def info(self, *args):
        self.debug(*args)

class FakeBinning():

    def __init__(self, bin_num=32):
        self.bin_num = bin_num

    def helper(self, instance, split_points):
        feat = instance.features
        sparse_feat = []
        indices = []
        for idx,  v in enumerate(feat):
            sparse_feat.append(np.argmax(split_points[idx] > v) - 1)
            indices.append(idx)
        return Instance(inst_id=instance.inst_id, features=SparseVector(indices=indices, data=sparse_feat)
                        , label=instance.label)

    def fit(self, Dtable:DTable):
        arr = []
        for row in Dtable.collect():
            arr.append(row[1].features)

        arr = np.stack(arr)
        split_points = []
        width = arr.shape[1]
        for num in range(width):
            col_max = arr[:, num].max()
            col_min = arr[:, num].min()
            split_points.append(np.arange(col_min, col_max, (col_max-col_min)/self.bin_num))

        self.split_points = np.stack(split_points)

        func = functools.partial(self.helper, split_points=self.split_points)
        new_table = Dtable.mapValues(func)
        return new_table, self.split_points, {k:0 for k in range(self.bin_num)}

# LOGGER = LocalTestLogger()

class HomoSecureBoostingTreeClient(BoostingTree):

    def __init__(self):
        super(HomoSecureBoostingTreeClient,  self).__init__()

        self.mode = consts.HOMO
        self.validation_strategy = None
        self.loss_fn = None
        self.cur_sample_weights = None
        self.y = None
        self.y_hat = None
        self.y_hat_predict = None
        self.tree_dim = 1
        self.feature_num = None
        self.num_classes = 2
        self.trees = []
        self.transfer_inst = HomoSecureBoostingTreeTransferVariable()
        self.role = None


    def set_loss_function(self, objective_param):
        loss_type = objective_param.objective
        params = objective_param.params
        LOGGER.info("set objective,  objective is {}".format(loss_type))
        if self.task_type == consts.CLASSIFICATION:
            if loss_type == "cross_entropy":
                if self.num_classes == 2:
                    self.loss_fn = SigmoidBinaryCrossEntropyLoss()
                else:
                    self.loss_fn = SoftmaxCrossEntropyLoss()
            else:
                raise NotImplementedError("objective %s not supported yet" % (loss_type))
        elif self.task_type == consts.REGRESSION:
            if loss_type == "lse":
                self.loss_fn = LeastSquaredErrorLoss()
            elif loss_type == "lae":
                self.loss_fn = LeastAbsoluteErrorLoss()
            elif loss_type == "huber":
                self.loss_fn = HuberLoss(params[0])
            elif loss_type == "fair":
                self.loss_fn = FairLoss(params[0])
            elif loss_type == "tweedie":
                self.loss_fn = TweedieLoss(params[0])
            elif loss_type == "log_cosh":
                self.loss_fn = LogCoshLoss()
            else:
                raise NotImplementedError("objective %s not supported yet" % (loss_type))
        else:
            raise NotImplementedError("objective %s not supported yet" % (loss_type))

    def federated_binning(self,  data_instance) -> Tuple[DTable, np.array, dict]:

        # federated binning

        # LOGGER.info('convert feature to bin')
        # parameter = FeatureBinningParam(bin_num=self.bin_num)
        # binning_obj = QuantileBinning(parameter , abnormal_list=[NoneType()] if self.use_missing else None)
        # binning_obj.fit_split_points(data_instance)
        # binned_data, bin_split_points, bin_sparse_points = binning_obj.convert_feature_to_bin(data_instance)
        #
        # LOGGER.info('converting feature to bin done')
        # return binned_data , bin_split_points , bin_sparse_points

        binning = FakeBinning(bin_num=10)
        return binning.fit(data_instance)

    def compute_local_grad_and_hess(self , y_hat):

        loss_method = self.loss_fn
        if self.task_type == consts.CLASSIFICATION:
            grad_and_hess = self.y.join(y_hat,  lambda y,  f_val: \
                (loss_method.compute_grad(y,  loss_method.predict(f_val)),  \
                 loss_method.compute_hess(y,  loss_method.predict(f_val))))
        else:
            grad_and_hess = self.y.join(y_hat,  lambda y,  f_val:
            (loss_method.compute_grad(y,  f_val), 
             loss_method.compute_hess(y,  f_val)))

        return grad_and_hess

    def compute_local_loss(self , y :DTable , y_hat :DTable):

        LOGGER.info('computing local loss')

        loss_method = self.loss_fn
        if self.objective_param.objective in ["lse",  "lae",  "logcosh",  "tweedie",  "log_cosh",  "huber"]:
            # regression tasks
            y_predict = y_hat
        else:
            # classification tasks
            y_predict = y_hat.mapValues(lambda val :loss_method.predict(val))

        loss = loss_method.compute_loss(y , y_predict)

        return float(loss)

    def sample_valid_feature(self):

        if self.feature_num is None:
            self.feature_num = self.bin_split_points.shape[0]

        chosen_feature = random.choice(range(0,  self.feature_num),  \
                                       max(1,  int(self.subsample_feature_rate * self.feature_num)),  replace=False)
        valid_features = [False for i in range(self.feature_num)]
        for fid in chosen_feature:
            valid_features[fid] = True

        return valid_features

    @staticmethod
    def add_y_hat(f_val , new_f_val , lr=0.1 , idx=0):
        f_val[idx] += lr * new_f_val
        return f_val

    def initialize_y_hat(self):
        return self.loss_fn.initialize(self.y) if self.tree_dim == 1 else \
            self.loss_fn.initialize(self.y,  self.tree_dim)

    def update_y_hat_val(self,  new_val=None,  mode='train',  tree_idx=0):

        LOGGER.debug('update y_hat value,  current tree is {}'.format(tree_idx))
        add_func = functools.partial(self.add_y_hat,  lr=self.learning_rate,  idx=tree_idx)
        if mode == 'train':
            self.y_hat = self.y_hat.join(new_val, add_func)
        else:
            self.y_hat_predict = self.y_hat_predict.join(new_val, add_func)

    def sync_feature_num(self):
        self.transfer_inst.feature_number.remote(self.feature_num, role=consts.ARBITER, idx=-1, suffix=(0, ))

    def fit(self,  data_inst:DTable, validate_data=None):

        # data_inst = self.data_alignment(data_inst)

        # sample num
        LOGGER.debug('sample number is {}'.format(data_inst.count()))

        # binning
        self.binned_data , self.bin_split_points , self.bin_sparse_points = self.federated_binning(data_inst)
        # set feature_num
        self.feature_num = self.bin_split_points.shape[0]
        # sending feature number to host
        self.sync_feature_num()
        # set loss function
        self.set_loss_function(self.objective_param)
        # set labels
        self.y = self.binned_data.mapValues(lambda instance :instance.label)
        # set y_hat_val
        self.y_hat,  self.init_score = self.loss_fn.initialize(self.y) if self.tree_dim == 1 else \
            self.loss_fn.initialize(self.y,  self.tree_dim)

        for epoch_idx in range(self.num_trees):

            g_h = self.compute_local_grad_and_hess(self.y_hat)
            valid_features = self.sample_valid_feature()
            new_tree = HomoDecisionTreeClient(self.tree_param,  self.binned_data,  self.bin_split_points, 
                                              self.bin_sparse_points,  g_h,  valid_feature=valid_features
                                              ,epoch_idx=epoch_idx, role=self.role, flow_id=epoch_idx)
            new_tree.fit()
            self.update_y_hat_val(new_val=new_tree.sample_weights,  mode='train',  tree_idx=0)
            self.trees.append(new_tree)
            loss = self.compute_local_loss(self.y , self.y_hat)

            LOGGER.debug('predicted val')
            LOGGER.debug(list(self.y_hat.collect()))
            LOGGER.debug('fitting one tree done, cur local loss is {}'.format(loss))

    def predict(self,  data_inst:DTable):

        to_predict_data = self.data_alignment(data_inst)

        self.y_hat_predict, _ = self.initialize_y_hat()

        for tree in self.trees:
            predict_val = tree.predict(to_predict_data)
            self.update_y_hat_val(new_val=predict_val, mode='predict')

        predict_result = None
        if self.task_type == consts.REGRESSION and \
                self.objective_param.objective in ["lse",  "lae",  "huber",  "log_cosh",  "fair",  "tweedie"]:
            predict_result = data_inst.join(self.y_hat_predict, \
                                    lambda inst,  pred: [inst.label,  float(pred),  float(pred),  {"label": float(pred)}])

        elif self.task_type == consts.CLASSIFICATION:
            if self.num_classes == 2:
                classes_ = [0, 1]
                threshold = self.predict_param.threshold
                predict_result = data_inst.join(self.y_hat_predict,  lambda inst,  pred: [inst.label, 
                                                                              classes_[1] if pred > threshold else
                                                                              classes_[0],  pred, 
                                                                              {"0": 1 - pred,  "1": pred}])
            else:
                # TODO multiclass
                pass

        return predict_result
