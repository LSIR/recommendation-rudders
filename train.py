import json
from pathlib import Path
from absl import app, flags, logging
import numpy as np
import tensorflow as tf

from rudders.config import CONFIG
from rudders.utils import setup_logger
from rudders.dataset import Dataset
import rudders.models as models
import rudders.losses as losses
from rudders.runner import Runner

flag_fns = {
    'string': flags.DEFINE_string,
    'integer': flags.DEFINE_integer,
    'boolean': flags.DEFINE_boolean,
    'float': flags.DEFINE_float,
}
for dtype, flag_fn in flag_fns.items():
    for arg, (description, default) in CONFIG[dtype].items():
        flag_fn(arg, default=default, help=description)
FLAGS = flags.FLAGS


def get_models(n_users, n_items):
    tf.keras.backend.set_floatx(FLAGS.dtype)
    model = getattr(models, FLAGS.model)(n_users, n_items, FLAGS)
    model.build(input_shape=(1, 2))
    params = sum(np.prod(x.shape) for x in model.trainable_variables)
    logging.info(f'Total number of trainable parameters: {params}')
    return model


def load_data(prep_path, dataset_name, debug):
    dataset_path = Path(prep_path) / dataset_name
    logging.info(f"Loading data from {dataset_path}")
    dataset = Dataset(dataset_path, debug)
    train = dataset.get_split('train')
    dev = dataset.get_split('dev')
    test = dataset.get_split('test')
    samples = dataset.get_samples()
    n_users, n_items = dataset.get_shape()
    logging.info(f'Dataset stats: n_users: {n_users}, n_items: {n_items}')
    return train, dev, test, samples, n_users, n_items


def save_config(logs_dir):
    config_path = logs_dir / 'config.json'
    if FLAGS.save_logs and not config_path.exists():
        with tf.io.gfile.GFile(str(config_path), 'w') as fjson:
            json.dump(get_config_dict(CONFIG), fjson)


def get_config_dict(external_config):
    """Maps FLAGS to dictionary in order to save it in json format."""
    config = {}
    for _, arg_dict in external_config.items():
        for arg, _ in arg_dict.items():
            config[arg] = getattr(FLAGS, arg)
    return config


def get_optimizer(args):
    if args.optimizer == 'adagrad':
        return tf.keras.optimizers.Adagrad(learning_rate=args.lr, initial_accumulator_value=0.0, epsilon=1e-10)
    if args.optimizer == 'adam':
        return tf.keras.optimizers.Adam(learning_rate=args.lr, epsilon=1e-08)
    return getattr(tf.keras.optimizers, args.optimizer)(learning_rate=args.lr)


def main(_):
    logs_dir = Path(FLAGS.logs_dir)
    setup_logger(FLAGS.save_logs, debug=FLAGS.debug)
    tf.config.experimental_run_functions_eagerly(FLAGS.debug)  # see if this is necessary in tf2

    # save config
    save_config(logs_dir)

    # load data
    train, dev, test, samples, n_users, n_items = load_data(FLAGS.prep_dir, FLAGS.dataset, FLAGS.debug)

    model = get_models(n_users, n_items)
    optimizer = get_optimizer(FLAGS)
    loss_fn = getattr(losses, FLAGS.loss_fn)((n_users, n_items), FLAGS.neg_sample_size, FLAGS.double_neg, FLAGS.margin)

    runner = Runner(FLAGS, model, optimizer, loss=loss_fn, train=train, dev=dev, test=test, samples=samples)
    runner.run()
    logging.info("Done!")


if __name__ == '__main__':
    app.run(main)