import os, sys
sys.path.append(os.getcwd())

from models import get_pipeline, is_dummy
from copy import deepcopy
import argparse
import numpy as np
import wandb
from data import get_test_dataset
from commander import get_config, setup_trainer
from metrics import setup_metric
from toolbox.planner import DataHandler, Planner

def get_config_specific(value, config=None):
    if config is None: config = BASE_CONFIG
    config = deepcopy(config)
    if PROBLEM == 'sbm':
        p_inter = C-value/2
        p_outer = C+value/2
        config['data']['test']['problems'][PROBLEM]['p_inter'] = p_inter
        config['data']['test']['problems'][PROBLEM]['p_outer'] = p_outer
    elif PROBLEM in ('mcp', 'mcptrue', 'hhc'):
        config['data']['test']['problems'][PROBLEM][VALUE_NAME] = value
    else:
        raise NotImplementedError(f'Problem {PROBLEM} config modification not implemented.')
    return config

def get_values(trainer):
    logged = trainer.logged_metrics
    loss_name = 'test_loss/dataloader_idx_{}'
    metrics_name = 'test.metrics/dataloader_idx_{}'
    total_dict = {}
    for i, value in enumerate(VALUES):
        loss_value = logged[loss_name.format(i)]
        metrics_value = logged[metrics_name.format(i)]
        values_dict = {
            'loss': loss_value,
            'metrics': metrics_value
        }
        total_dict[f'{value:.4f}'] = values_dict
    return total_dict

def get_train_value(run):
    config = run.config
    if PROBLEM == 'sbm':
        p_outer = config['data']['train']['problems'][PROBLEM]['p_outer']
        p_inter = config['data']['train']['problems'][PROBLEM]['p_inter']
        value = p_outer-p_inter
    elif PROBLEM in ('mcp', 'hhc'):
        value = config['data']['train']['problems'][PROBLEM][VALUE_NAME]
    elif PROBLEM == 'mcptrue':
        value = config['data']['train']['problems']['mcp'][VALUE_NAME]
    else:
        raise NotImplementedError(f'Problem {PROBLEM} config modification not implemented.')
    return value

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Grid testing on the experiments from one W&B repository.')
    parser.add_argument('--skip', metavar='skip', type=int, default=0, help='Number of experiments to skip')
    args = parser.parse_args()

    SKIP_FIRST_N_RUNS=args.skip

    #VALUES_DEPENDING ON ABOVE
    BASE_PATH = 'scripts/'
    CONFIG_FILE_NAME = f'grid_dummy_config.yaml'
    CONFIG_FILE = os.path.join(BASE_PATH, CONFIG_FILE_NAME)
    BASE_CONFIG = get_config(CONFIG_FILE)

    #CONFIG DEPENDING
    PROBLEM = BASE_CONFIG['problem']
    
    print(f"Working on problem '{PROBLEM}'")
    if PROBLEM in ('mcp', 'mcptrue'):
        VALUE_NAME = 'clique_size'
        VALUES = range(5,20)
    elif PROBLEM == 'sbm':
        VALUE_NAME = 'dc'
        VALUES = np.linspace(0,6,25)
        C=3
    elif PROBLEM == 'hhc':
        VALUE_NAME = 'fill_param'
        l_musquare = np.linspace(0,25,26)
        VALUES = np.sqrt(l_musquare)
    else:
        raise NotImplementedError(f"Problem {PROBLEM} not implemented.")

    test_loaders = []
    
    arch_name = BASE_CONFIG['arch']['name']
    if not is_dummy(arch_name):
        raise TypeError(f"Model {arch_name} is not dummy.")

    for value in VALUES:
        config = get_config_specific(value)
        test_loaders.append(get_test_dataset(config))

    pl_model = get_pipeline(BASE_CONFIG)

    setup_metric(pl_model, BASE_CONFIG, istest=True)
    trainer = setup_trainer(BASE_CONFIG, pl_model, watch=False, only_test=True)
    print(f"Now testing dummy")
    trainer.test(pl_model, dataloaders=test_loaders)
    print(f"Testing finished.")
    if trainer.global_rank==0:
        summary = trainer.logger.experiment.summary
        summary['train_value'] = 'dummy'
        summary['values'] = [f"{value:.4f}" for value in VALUES]
        summary['logged'] = trainer.logged_metrics
    wandb.finish()
