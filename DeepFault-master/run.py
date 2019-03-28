# -*- coding:UTF-8 -*-
"""
This is the main file that executes the flow of DeepFault
"""

from test_nn import test_model
from lp import run_lp  # 好像没调用？
from os import path
from spectrum_analysis import *
from utils import save_perturbed_test_groups, load_perturbed_test_groups
from utils import load_suspicious_neurons, save_suspicious_neurons
from utils import create_experiment_dir, get_trainable_layers
from utils import load_classifications, save_classifications
from utils import save_layer_outs, load_layer_outs, construct_spectrum_matrices
from utils import load_MNIST, load_CIFAR, load_model
from utils import filter_val_set, save_original_inputs
from input_synthesis import synthesize
from sklearn.model_selection import train_test_split
import datetime
import argparse
import random

from keras.utils.vis_utils import plot_model
#from keras.utils.vis_utils import model_to_dot
#from IPython.display import SVG  # model即为要可视化的网络模型

experiment_path = "experiment_results"
model_path = "neural_networks"
group_index = 1   # 具体去看下是什么意思
__version__ = "v1.0"

def parse_arguments():
    """
    Parse command line argument and construct the DNN
    :return: a dictionary comprising the command-line arguments
    """

    # define the program description
    text = 'Spectrum Based Fault Localization for Deep Neural Networks'

    # initiate the parser
    parser = argparse.ArgumentParser(description=text)

    # add new command-line arguments
    parser.add_argument("-V", "--version",  help="show program version",
                        action="version", version="DeepFault " + __version__)
    parser.add_argument("-M", "--model",    help="The model to be loaded. The \
                        specified model will be analyzed.", required=True)
    parser.add_argument("-DS", "--dataset", help="The dataset to be used (mnist\
                        or cifar10).", choices=["mnist","cifar10"])
    parser.add_argument("-A", "--approach", help="the approach to be employed \
                        to localize dominant neurons")
    parser.add_argument("-D", "--distance",   help="the distance between the \
                        original and the mutated image.", type=float)
    parser.add_argument("-C", "--class", help="the label of inputs to \
                        analyze.", type= int)
    parser.add_argument("-AC", "--activation",     help="activation function \
                        or hidden neurons. it can be \"relu\" or \"leaky_relu\"")
    parser.add_argument("-SN", "--suspicious_num", help="number of suspicious \
                        neurons we consider", type=int)
    parser.add_argument("-SS", "--step_size",      help="multiplication of \
                        gradients by step size", type=float)
    parser.add_argument("-R", "--repeat",    help="index of the repeating. (for\
                        the cases where you need to run the same experiment \
                        multiple times)", type=int)
    parser.add_argument("-S", "--seed", help="Seed for random processes. \
                        If not provided seed will be selected randomly.", type=int)
    parser.add_argument("-ST", "--star", help="DStar\'s Star \
                        hyperparameter. Has an effect when selected approach is\
                        DStar", type=int)
    parser.add_argument("-LOG", "--logfile", help="path to log file")

    # parse command-line arguments
    args = parser.parse_args()

    return vars(args)



if __name__ == "__main__":
    args = parse_arguments()
    model_name     = args['model'] # model没有default值 需要通过命令行输入 "required=True"
    dataset        = args['dataset'] if not args['dataset'] == None else 'mnist'
    selected_class = args['class'] if not args['class'] == None else 0 # mnist有0-9共10个数字
    step_size      = args['step_size'] if not args['step_size'] == None else 1
    distance       = args['distance'] if not args['distance'] ==None else 0.1
    approach       = args['approach'] if not args['approach'] == None else 'tarantula' #关于suspicious neurons的统计方式
    susp_num       = args['suspicious_num'] if not args['suspicious_num'] == None else 1
    repeat         = args['repeat'] if not args['repeat'] == None else 1
    seed           = args['seed'] if not args['seed'] == None else random.randint(0,10)
    star           = args['star'] if not args['star'] == None else 3
    logfile_name   = args['logfile'] if not args['logfile'] == None else 'result.log'

    ####################
    # 0) Load MNIST or CIFAR10 data
    if dataset == 'mnist':
        X_train, Y_train, X_test, Y_test = load_MNIST()
        # New added!
        # X_train, Y_train, X_test, Y_test = load_MNIST(one_hot=True, channel_first=True)
    else:
        X_train, Y_train, X_test, Y_test = load_CIFAR()


    X_train, X_val, Y_train, Y_val = train_test_split(X_train, Y_train,   # train_test_split函数用于将矩阵随机划分为训练子集和测试子集，
                                                      test_size=1/6.0,    # 并返回划分好的训练集测试集样本和训练集测试集标签。
                                                   random_state=seed)  # 10000个test_case大致分到0-9每个数字class按照label
#for i in range(5):
#for susp_num in [1,2]:

    avg_loss = avg_acc = 0.

    for selected_class in range(10):

        logfile = open(logfile_name, 'a')


        ####################
        # 1) Load the pretrained network.
        try:
            model = load_model(path.join(model_path, model_name))   # utils里自定义的
        except:
            logfile.write("Model not found! Provide a pre-trained model model as input.\n")
            exit(1)

        # plot_model(model, to_file='model.png', show_shapes=True, show_layer_names=False)
        # SVG(model_to_dot(model).create(prog='dot', format='svg'))

        experiment_name = create_experiment_dir(experiment_path, model_name,  # utils里自定义的
                                                selected_class, step_size,
                                                approach, susp_num, repeat)

        #Fault localization is done per class.
        X_val, Y_val = filter_val_set(selected_class, X_test, Y_test)   # utils里自定义的

        ####################
        # 2)test the model and receive the indexes of correct and incorrect classifications
        # Also provide output of each neuron in each layer for test input x.
        filename = experiment_path + '/' + model_name + '_' + str(selected_class)  #C0, C1, ...

        plot_model(model, to_file= filename + '_model.png', show_shapes=True, show_layer_names=False)

        try:
            correct_classifications, misclassifications = load_classifications(filename, group_index)  # utils里自定义的
            layer_outs = load_layer_outs(filename, group_index)   # output of each neuron in each layer for test input x !!!
        except:
            correct_classifications, misclassifications, layer_outs, predictions =\
                    test_model(model, X_val, Y_val)
            # print("layer_outs: " + str(layer_outs))
            # print("correct_classifications: " + str(correct_classifications))
            print("misclassifications: " + str(misclassifications))
            # print("predictions: " + str(predictions))
            save_classifications(correct_classifications, misclassifications,
                                 filename, group_index)
            save_layer_outs(layer_outs, filename, group_index)


        ####################
        # 3) Receive the correct classifications  & misclassifications and identify
        # the suspicious neurons per layer
        trainable_layers = get_trainable_layers(model)
        scores, num_cf, num_uf, num_cs, num_us = construct_spectrum_matrices(model,
                                                                            trainable_layers,
                                                                            correct_classifications,
                                                                            misclassifications,
                                                                            layer_outs)

        filename = experiment_path + '/' + model_name + '_C' + str(selected_class) + '_' +\
        approach +  '_SN' +  str(susp_num)

        if approach == 'tarantula':
            try:
                suspicious_neuron_idx = load_suspicious_neurons(filename, group_index)
            except:
                suspicious_neuron_idx = tarantula_analysis(trainable_layers, scores,
                                                     num_cf, num_uf, num_cs, num_us,
                                                     susp_num)

                save_suspicious_neurons(suspicious_neuron_idx, filename, group_index)

        elif approach == 'ochiai':
            try:
                suspicious_neuron_idx = load_suspicious_neurons(filename, group_index)
            except:
                suspicious_neuron_idx = ochiai_analysis(trainable_layers, scores,
                                                     num_cf, num_uf, num_cs, num_us,
                                                     susp_num)

                save_suspicious_neurons(suspicious_neuron_idx, filename, group_index)

        elif approach == 'dstar':
            try:
                suspicious_neuron_idx = load_suspicious_neurons(filename, group_index)
            except:
                suspicious_neuron_idx = dstar_analysis(trainable_layers, scores,
                                                     num_cf, num_uf, num_cs, num_us,
                                                     susp_num, star)

                save_suspicious_neurons(suspicious_neuron_idx, filename, group_index)

        elif approach == 'random': # 个人认为作者的random并不是真正的random
            # Random fault localization has to be run after running Tarantula,
            # Ochiai and DStar with the same parameters.

            '''filename = experiment_path + '/' + model_name + '_C' + str(selected_class) \
            + '_tarantula_' + 'SN' + str(susp_num)

            suspicious_neuron_idx_tarantula = load_suspicious_neurons(filename, group_index)

            filename = experiment_path + '/' + model_name + '_C' + str(selected_class) \
            + '_ochiai_' + 'SN' + str(susp_num)

            suspicious_neuron_idx_ochiai = load_suspicious_neurons(filename, group_index)

            filename = experiment_path + '/' + model_name + '_C' + str(selected_class) \
            + '_dstar_' + 'SN' + str(susp_num)

            suspicious_neuron_idx_dstar = load_suspicious_neurons(filename, group_index)

            forbiddens = suspicious_neuron_idx_ochiai + suspicious_neuron_idx_tarantula  + \
            suspicious_neuron_idx_dstar

            forbiddens = [list(forb) for forb in forbiddens]

            available_layers = list(([elem[0] for elem in suspicious_neuron_idx_tarantula]))
            available_layers += list(set([elem[0] for elem in suspicious_neuron_idx_ochiai]))
            available_layers += list(set([elem[0] for elem in suspicious_neuron_idx_dstar]))'''

            suspicious_neuron_idx = []
            while len(suspicious_neuron_idx) < susp_num:
                #l_idx = random.choice(available_layers)
                l_idx = random.choice(trainable_layers)
                n_idx = random.choice(range(model.layers[l_idx].output_shape[1]))

                #if [l_idx, n_idx] not in forbiddens and [l_idx, n_idx] not in suspicious_neuron_idx:
                if [l_idx, n_idx] not in suspicious_neuron_idx:
                    suspicious_neuron_idx.append([l_idx, n_idx])


        # logfile.write('Suspicous neurons: ' + str(suspicious_neuron_idx) + '\n')



        ####################
        # 4) Run Suspiciousness-Guided Input Synthesis Algorithm
        # Receive the set of suspicious neurons for each layer from Step 3 # and
        # will produce new inputs based on the correct classifications (from the
        # testing set) that exercise the suspicious neurons

        loss = acc = 0.

        # for i in range(5):
        perturbed_xs = []    # 初始化目标输出
        perturbed_ys = []

    # select 10 inputs randomly from the correct classification set.
        selected = np.random.choice(list(correct_classifications), 10)   # 一定要从正确集里面选 问题：有没有别的选法？ e.g. 根据suspicious neurons目前的激活值？
        zipped_data = zip(list(np.array(X_val)[selected]), list(np.array(Y_val)[selected]))  # X_val/Y_val都是属于 correct_classification 里面的
    # zip() 函数用于将可迭代的对象作为参数，将对象中对应的元素打包成一个个元组，然后返回由这些元组组成的列表。如需展示列表，需手动 list() 转换。

        syn_start = datetime.datetime.now() # 为了判断生成 perturbed_inputs 的时间
        x_perturbed, y_perturbed, x_original = synthesize(model, zipped_data,
                                           suspicious_neuron_idx,
                                           correct_classifications,
                                           step_size,
                                           distance)
        syn_end = datetime.datetime.now()


        perturbed_xs = perturbed_xs + x_perturbed # 等价于直接赋值？
        perturbed_ys = perturbed_ys + y_perturbed

    # reshape them into the expected format
        perturbed_xs = np.asarray(perturbed_xs).reshape(np.asarray(perturbed_xs).shape[0],
                                     *X_val[0].shape)  # numpy.asarray(a, dtype = None, order = None) 将输入转化成数组
        perturbed_ys = np.asarray(perturbed_ys).reshape(np.asarray(perturbed_ys).shape[0], 10)


    #save perturtbed inputs
        filename = path.join(experiment_path, experiment_name)

    # filename = path.join(filename, str(i))

        save_perturbed_test_groups(perturbed_xs, perturbed_ys, filename, group_index)
    # New added!
    # save_perturbed_test_groups(x_perturbed, y_perturbed, filename, group_index)
        save_original_inputs(x_original, filename, group_index)


    ####################
    # 5) Test if the mutated inputs are adversarial
        score = model.evaluate(perturbed_xs, perturbed_ys, verbose=0)

        loss = loss + score[0]
        acc = acc + score[1]
        #logfile.write('Model: ' + model_name + ', Class: ' + str(selected_class) +
        #              ', Approach: ' + approach + ', Distance: ' +
        #              str(distance) + ', Avg_loss: ' + str(loss) + ', Avg_acc: ' + str(acc) + '\n')

        avg_loss += loss
        avg_acc += acc
        """
        score_val = model.evaluate(X_val, Y_val) # num = 980
        print("score_val" + str(score_val))
        score_tr = model.evaluate(X_train, Y_train) # num = 50000
        print("score_tr" + str(score_tr))
        score_test = model.evaluate(X_test, Y_test) # num = 10000
        print("score_test" + str(score_test))
        """

        # New added!
        # score = model.evaluate([x_perturbed], [y_perturbed], verbose=0)

        # logfile.write('Round: ' + str(i))
        logfile.write('Model: ' + model_name + ', Class: ' + str(selected_class) +
                      ', Approach: ' + approach + ', Distance: ' +
                      str(distance) + ', Score: ' + str(score) + '\n')

        '''logfile.write('Input Synthesis Time: ' + str(syn_end-syn_start) + '\n')
        
        logfile.write("loss: " + str(loss) + ', acc: ' + str(acc) + '\n')'''


    logfile.write('the loss for k = ' + str(susp_num) + ', Approach: ' + str(approach) + ', Loss ='+
                  str(avg_loss/10) + ', Accuracy: ' + str(avg_acc/10) + '\n')
    logfile.close()


'''
    Currently not available
    ####################
    # 6) retrain the model
    # train_model_fault_localisation(model, x_perturbed, y_perturbed, len(x_perturbed))
    model.fit(x_perturbed, y_perturbed, batch_size=32, epochs=10, verbose=1)

    ####################
    # 7) retest the model
    test_model(model, X_test, Y_test)
'''
