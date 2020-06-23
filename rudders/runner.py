import time
import copy
import tensorflow as tf
import numpy as np
from absl import logging
from pathlib import Path
from rudders.utils import rank_to_metric_dict


class Runner:
    def __init__(self, args, model, optimizer, loss, train, dev, test, samples):
        self.args = args
        self.model = model
        self.optimizer = optimizer
        self.loss_fn = loss
        self.train = train
        self.dev = dev
        self.test = test
        self.samples = samples
        self.summary = tf.summary.create_file_writer(args.logs_dir + "/summary")
        # self.ckpt_manager = self.setup_manager()

    def run(self):
        best_hr_at_10 = best_epoch = early_stopping_counter = 0
        best_weights = None

        for epoch in range(1, self.args.max_epochs + 1):
            train_loss, exec_time = self.train_epoch()

            logging.info(f'Epoch {epoch} | train loss: {train_loss:.4f} | total time: {int(exec_time)} secs')
            with self.summary.as_default():
                tf.summary.scalar('train/loss', train_loss, step=epoch)

            # if self.args.save_model and epoch % self.args.checkpoint == 0:
            #     logs_dir = self.manager.save()
            #     logging.info(f'Saved checkpoint for epoch {epoch}: {logs_dir}')

            if epoch % self.args.validate == 0:
                dev_loss = self.validate()

                logging.info(f'Epoch {epoch} | average valid loss: {dev_loss:.4f}')
                with self.summary.as_default():
                    tf.summary.scalar('dev/loss', dev_loss, step=epoch)

                # compute validation metrics
                _, metric_random = self.compute_metrics(self.dev, "dev", epoch)

                # early stopping
                hr_at_10 = metric_random["HR@10"]
                if hr_at_10 > best_hr_at_10:
                    best_hr_at_10 = hr_at_10
                    early_stopping_counter = 0
                    best_epoch = epoch
                    best_weights = copy.copy(self.model.get_weights())
                else:
                    early_stopping_counter += 1
                    if early_stopping_counter == self.args.patience:
                        logging.info('Early stopping!!!')
                        break

        logging.info(f'Optimization finished\nEvaluating best model from epoch {best_epoch}')
        self.model.set_weights(best_weights)

        if self.args.save_model:
            self.model.save_weights(Path(self.args.logs_dir) / 'best_model.ckpt')

        # validation metrics
        logging.info(f"Final performance after {epoch} epochs")
        self.compute_metrics(self.dev, "dev", epoch, write_summary=False)
        self.compute_metrics(self.test, "test", epoch, write_summary=False)

    def compute_metrics(self, split, title, epoch, write_summary=True):
        random_items = 100
        rank_all, rank_random = self.model.random_eval(split, self.samples, num_rand=random_items)
        metric_all, metric_random = rank_to_metric_dict(rank_all), rank_to_metric_dict(rank_random)

        logging.info(f"Result at epoch {epoch} in {title.upper()}")
        logging.info(f"Random items {random_items}:" + " ".join((f"{k}: {v:.2f}" for k, v in metric_random.items())))
        logging.info("All items:" + " ".join((f"{k}: {v:.2f}" for k, v in metric_all.items())))

        if write_summary:
            with self.summary.as_default():
                for k, v in metric_random.items():
                    tf.summary.scalar(f"{k}_r", v, step=epoch)
                for k, v in metric_all.items():
                    tf.summary.scalar(k, v, step=epoch)

        return metric_all, metric_random

    def train_epoch(self):
        train_batch = self.train.batch(self.args.batch_size)
        total_loss = np.zeros(1)    # tf.keras.backend.constant(0.0)
        counter = np.zeros(1)       # tf.keras.backend.constant(0.0)
        start = time.perf_counter()
        for input_batch in train_batch:
            counter += 1.0
            with tf.GradientTape() as tape:
                loss = self.loss_fn.calculate_loss(self.model, input_batch)

            gradients = tape.gradient(loss, self.model.trainable_variables)
            self.optimizer.apply_gradients(zip(gradients, self.model.trainable_variables))
            total_loss += loss.numpy()

        total_loss /= counter
        exec_time = time.perf_counter() - start
        return total_loss, exec_time

    def validate(self):
        dev_batch = self.dev.batch(self.args.batch_size)
        total_loss = np.zeros(1)  # tf.keras.backend.constant(0.0)
        counter = np.zeros(1)  # tf.keras.backend.constant(0.0)
        for input_batch in dev_batch:
            counter += 1.0
            loss = self.loss_fn.calculate_loss(self.model, input_batch)
            total_loss += loss.numpy()

        return total_loss / counter

    def setup_manager(self):
        # TODO: see how to use this
        if not self.args.save_model:
            return None
        ckpt = tf.train.Checkpoint(step=tf.Variable(0), optimizer=self.optimizer, net=self.model)
        manager = tf.train.CheckpointManager(ckpt, self.args.logs_dir, max_to_keep=1)
        if manager.latest_checkpoint:
            ckpt.restore(manager.latest_checkpoint)
            logging.info(f'Restored from {manager.latest_checkpoint}')
        return manager
