'''
This is a python file that used for training GAN.
TODO: provide a parser access from terminal.
'''
## Import module
import sys, os
root_dir = os.path.dirname(os.getcwd())
sys.path.append(root_dir)
import numpy as np
import tensorflow as tf
from time import strftime
from datetime import datetime
from pytz import timezone

from Inputpipeline.mnistDataset import mnistDataSet as DataSet
from Training.train_base import Train_base
from Training.Saver import Saver
from Training.Summary import Summary
from utils import *
# import Training.utils as utils
# from Training.utils import initialize_uninitialized_vars

class Train(Train_base):
    def __init__(self, config, log_dir, save_dir, **kwargs):
        super(Train, self).__init__(config.LEARNING_RATE, config.BETA1)
        self.config = config
        self.save_dir = save_dir
        self.comments = kwargs.get('comments', '')
        if self.config.SUMMARY:
            self.summary = Summary(log_dir, config, \
                                       log_comments=kwargs.get('comments', ''))

    def train(self, Model):
        # Reset tf graph.
        tf.reset_default_graph()

        # Create input node
        image_batch, label_batch, init_op, dataset = self._input_fn()

        # Build up the graph and loss
        with tf.device('/gpu:0'):
            # Create placeholder
            if self.config.NUM_CLASSES:
                y = tf.placeholder(tf.float32, [self.config.BATCH_SIZE, self.config.NUM_CLASSES], name='y') # label batch
            else:
                y = None

            x = tf.placeholder(tf.float32, [self.config.BATCH_SIZE] + self.config.IMAGE_DIM, name='real_images') # real image
            z = tf.placeholder(tf.float32, [None, self.config.Z_DIM]) # latent variable

            # Build up the graph
            G, D, D_logits, D_, D_logits_, z, model = training._build_train_graph(x, y, z, Model)
            # Create the loss:
            d_loss, g_loss = self._loss(D, D_logits, D_, D_logits_)

            # Sample the generated image every epoch
            samples = model.sampler(z, label_batch)

        # Create optimizer
        with tf.name_scope('Train'):
            t_vars = tf.trainable_variables()
            theta_G = [var for var in t_vars if 'g_' in var.name]
            theta_D = [var for var in t_vars if 'd_' in var.name]

            optimizer = self._Adam_optimizer()
            g_optim = self._train_op(optimizer, g_loss, theta_G)
            d_optim = self._train_op(optimizer, d_loss, theta_D)




        ## TODO: add summary

        ## TODO: add saver


        # Create Session
        sess_config = tf.ConfigProto(allow_soft_placement = True)
        # Use soft_placement to place those variables, which can be placed, on GPU
        with tf.Session(config = sess_config) as sess:
            if self.config.RESTORE:
                ## TODO
                pass
            else:
                start_epoch = 0
                # initialize the variables
                init_var = tf.group(tf.global_variables_initializer(), \
                                    tf.local_variables_initializer())
                sess.run(init_var)
            sess.run(init_op)
            sample_z = np.random.uniform(-1, 1, size=(64, 100))
            sample_x, sample_y = sess.run([image_batch, label_batch])


            # Start Training
            tf.logging.info("Start traininig!")
            for epoch in range(start_epoch + 1, self.config.EPOCHS + 1):
                tf.logging.info("Training for epoch {}.".format(epoch))
                train_pr_bar = tf.contrib.keras.utils.Progbar(target= \
                                                                  int(self.config.TRAIN_SIZE / self.config.BATCH_SIZE))
                sess.run(init_op)
                for i in range(int(self.config.TRAIN_SIZE / self.config.BATCH_SIZE)):
                    batch_z = np.random.uniform(-1, 1, [self.config.BATCH_SIZE, 100]).astype(np.float32)
                    # Fetch a data batch
                    image_batch_o, label_batch_o = sess.run([image_batch, label_batch])

                    # Update discriminator
                    _, d_loss_o = sess.run([d_optim, d_loss],
                                feed_dict = {x: image_batch_o,
                                             y: label_batch_o,
                                             z: batch_z})
                    # Update generator
                    _ = sess.run([g_optim],
                                 feed_dict = {y: label_batch_o,
                                              z: batch_z})
                    _, g_loss_o = sess.run([g_optim, g_loss],
                                 feed_dict = {y: label_batch_o,
                                              z: batch_z})

                    # Update progress bar
                    train_pr_bar.update(i)
                print("Epoch: [%2d/%2d], d_loss: %.8f, g_loss: %.8f" \
                      % (epoch, self.config.EPOCHS, d_loss_o, g_loss_o))

                ## Sample image after every epoch
                samples_o, d_loss_o, g_loss_o = sess.run([samples, d_loss, g_loss],
                                                   feed_dict = {x: sample_x,
                                                                y: sample_y,
                                                                z: sample_z})
                print("[Sample] d_loss: %.8f, g_loss: %.8f" % (d_loss_o, g_loss_o))
                save_images(samples_o, image_manifold_size(samples_o.shape[0]), './samples/train_{:02d}.png'.format(epoch))


    def _loss(self, D, D_logits, D_, D_logits_):
        with tf.name_scope('Loss'):
            # Discriminator loss
            d_loss_real = self._sigmoid_cross_entopy_w_logits(tf.ones_like(D), D_logits)
            d_loss_fake = self._sigmoid_cross_entopy_w_logits(tf.zeros_like(D_), D_logits_)
            d_loss = d_loss_fake + d_loss_real
            # Generator loss
            g_loss = self._sigmoid_cross_entopy_w_logits(tf.ones_like(D_), D_logits_)
        return d_loss, g_loss

    def _build_train_graph(self, x, y, z, Model):
        """
        Build up the training graph
        :return:
        G: generated image batch
        D: probability (after sigmoid)
        D_logits: logits before sigmoid
        D_: probability for fake data
        D_logits_: logits before sigmoid for fake data
        """
        ## Create the model
        main_graph = Model(self.config)
        G, D, D_logits, D_, D_logits_ = main_graph.forward_pass(z, x, y)
        return G, D, D_logits, D_, D_logits_, z, main_graph


    def _input_fn(self):
        """
        Create the input node
        :return:
        """
        with tf.device('/cpu:0'):
            with tf.name_scope('Input_Data'):
                # Training dataset
                dataset = DataSet(self.config.DATA_DIR, self.config, 'train')
                # Inputpipeline
                image_batch, label_batch, init_op = dataset.inputpipline_singleset()
        return image_batch, label_batch, init_op, dataset


if __name__ == "__main__":
    from config import Config
    from Model.DCGAN import DCGAN as Model

    tf.logging.set_verbosity(tf.logging.INFO)
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Disable all debugging logs

    class tempConfig(Config):
        BATCH_SIZE = 64
        RESTORE = False
        TRAIN_SIZE = 70000
        DATA_DIR = os.path.join(root_dir, "Dataset/mnist")
        EPOCHS = 25

    tmp_config = tempConfig()

    # Folder to save the trained weights
    save_dir = "Training/Weights"
    # Folder to save the tensorboard info
    log_dir = "Training/Log"
    # Comments log on the current run
    comments = "This training is for creating a developed API."
    comments += tmp_config.config_str() + datetime.now(timezone('US/Eastern')).strftime("%Y-%m-%d_%H_%M_%S")
    # Create a training object
    training = Train(tmp_config, log_dir, save_dir, comments=comments)
    training.train(Model)