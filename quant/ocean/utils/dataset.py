import numpy as np
import pandas as pd 
import matplotlib.pyplot as plt 
import seaborn 


class DataSet(pd.DataFrame):
    context = {} 
    display_columns = ['stock_name', 'date', 'val_f_', 'pred_', '_pred'] 
    
    training_set = None
    test_set = None 
    
    model = 'linear_model'
    default_label = None
    default_test_ratio = 0.2
    
    
    @property
    def _constructor(self):
        return DataSet
    
    def __iadd__(self, df):
        self = self.append(df)
        return self
    
    
    # ================ Quick Functions =============== # 
    
    def _head(self, n=3):
        return self[self.display_columns].head(n)
    
    def _tail(self, n=3):
        return self[self.display_columns].tail(n)
    
    def mse(self, pred=None, label=None):
        if label is None:
            assert self.default_label is not None, "no label and no default label"
            label = self.default_label
            print("use default label: ", label)
        
        return np.mean((self[pred] - self[label]) ** 2)
    
    
    def summary(self):
        display_columns = list(filter(lambda s: s in self.display_columns, self.columns))
        df = self[display_columns]
        summary_df = df.describe()
        return summary_df
    
    def get_label(self):
        return self[self.default_label]
    
    def add_display(self, *args):
        for s in args:
            self.display_columns.append(s)
    
    
    # ================ Predictive Models  =============== # 
    
    def split(self, test_ratio=None, split_point=None, split_field='date'):
        """
        do training set - test set splitting by split_point of split_field
        Args:
            test_ratio: test set ratio, will be override if split_point is not None
            split_point: should be of the same type as df[split_field]
            split_field: must be in df.columns
        Returns:
            self.training_set, self.test_set 
        """
        
        assert split_field in self.columns, "field is not found: %s" % split_field
        
        test_ratio = self.default_test_ratio if test_ratio is None else test_ratio
        assert test_ratio is not None
        self.default_test_ratio = test_ratio
        
        df = self
        sample_num = df.shape[0] 
        if split_point is None:
            df = df.sort_index(by=split_field, ascending=True)
            split_point = df[split_field][int(sample_num * (1 - test_ratio))]
        
        self.training_set = df[df[split_field] <= split_point]
        self.test_set = df[df[split_field] > split_point]
        
        train_num = self.training_set.shape[0] 
        test_num = self.test_set.shape[0]
        
        sample_num = float(sample_num)
        print("training set: sample num = %s, raito = %.3f" % (train_num, train_num / sample_num))
        print("test set: sample num = %s, ratio = %.3f" % (test_num, test_num / sample_num)) 
  
    
    def fit(self, *args, **kargs) :
        print('model: %s'% self.model)
        if self.model == 'linear_model':
            return self.linear_model(*args, **kargs)
        else:
            raise NotImplementedError()     
    
    def linear_model(self, 
                     features=[], 
                     label=None, 
                     l2=1e-4, 
                     append_prediction=True, 
                     return_dict = False):
        
        if label is None:
            assert self.default_label is not None, "no label and no default label"
            label = self.default_label
            print("use default label: ", label)
        else:
            self.default_label = label
           
        training_set = self.training_set
        test_set = self.test_set 
        
        if (training_set is None) or (test_set is None):
            print("no training set - test set splitting")
            print("use full dataset as both training set and test set")
            training_set = self 
            test_set = self
            
        X = np.array(training_set[features].values)
        Y = np.array(training_set[label].values) 
        
        _, d = X.shape
        
        # explanatory model: with future features
        beta = np.linalg.inv(X.T.dot(X) + l2 * np.eye(d)).dot(X.T).dot(Y)
        coeff_dict = dict(zip(features, beta))
        
        # predictive model: no future features
        features_ = list(filter(lambda s: s[0] != '_', features)) 
        beta_ = np.array([coeff_dict[fea] for fea in features_])
        

        def mse(df):
            pred = np.array(df[features].dot(beta))
            Y = np.array(df[label])
            return np.mean((Y - pred) ** 2) 
        
        def mse_(df):
            pred_ = np.array(df[features_].dot(beta_))
            Y = np.array(df[label])
            return np.mean((Y - pred_) ** 2) 
               
        
        print("training explanatory MSE: %.6f " % mse(training_set))
        print("test set explanatory MSE: %.6f" % mse(test_set))
        
        print("training predictive MSE: %.6f" % mse_(training_set))
        print("test set predictive MSE: %.6f" % mse_(test_set))

        # append prediction 
        if append_prediction:
            self['_pred'] = np.array(self[features]).dot(beta)
            self['pred_'] = np.array(self[features_]).dot(beta_)
            self['_err'] = np.array(self[label] - self['_pred'])
            self.split()

        if return_dict:
            return coeff_dict
        
        coeff_df = pd.DataFrame.from_dict(coeff_dict, orient='index')
        coeff_df.columns = ['coeff']
        coeff_df = coeff_df.reindex(index = features)
        return coeff_df
    
    # ================ Analysis  =============== # 
    def get_reward(self, signal, threshold, label=None, mode='test'):
        label = self.default_label if label is None else label 
        assert label is not None
        self.default_label = label
        
        if mode == 'test':
            df = self.test_set
        elif mode == 'train':
            df = self.training_set 
        else:
            df = self
        
        df['is_candidate'] = (df[signal] > threshold)
        return df[df['is_candidate']][label].mean()
    
    def plot_rewards(self, signal, percentage=True, label=None, mode='test'):
        if type(signal) == list:
            for s in signal:
                self.plot_rewards(s, percentage, label, mode)
            plt.title('top-k %s average reward (%s set)' % (signal, mode))
            plt.xlabel(str(signal) + ' percentage')
            
            plt.legend('best', labels=signal)
        else:
            plt.figure(figsize=[8,5])
            signal_list =  np.sort(self[signal])
            x_list = []
            y_list = []
            percent_list = [] 
            for i in range(100):
                x = signal_list[i / 100.0 * len(signal_list)]
                y = self.get_reward(signal, x, label=label, mode=mode)
                
                percent_list.append(i)
                x_list.append(x)
                y_list.append(y)
            
            plt.title('top-k [%s] average reward (%s set)' % (signal, mode)) 
            if percentage:
                plt.scatter(percent_list, y_list, s = 10, label=signal)
                plt.xlabel(signal + ' percentage')
            else:
                plt.scatter(x_list, y_list, s = 10, label=signal)
                plt.xlabel(signal)
                
            plt.ylabel('reward')

    def hist(self, field, a_min, a_max, bins=20):
        x = self[field]
        a_min = min(x) if a_min is None else a_min
        a_max = max(x) if a_max is None else a_max
        plt.hist(self[field].clip(a_min, a_max).values, bins=bins)
        plt.xlabel(field)
        plt.title(field)
        
    def hist_err(self, bins=20):
        self.hist('_err', a_min=-0.1, a_max=0.1, bins=bins)
        
        
        