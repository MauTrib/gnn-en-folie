import sys, os
sys.path.append(os.getcwd())
import tqdm
from data import get_test_dataset
from toolbox.planner import DataHandler
from commander import get_config, load_model, setup_metric, setup_trainer
import wandb
import numpy as np

PROBLEM = 'sbm'
VALUE_NAME = 'dc'
MODEL = 'fgnn'
MODELS_DIR = f'observers/repr_{PROBLEM}/'
BASE_PATH = f'scripts/{MODEL}/'
DATA_FILE = os.path.join(BASE_PATH, f'planner_files/recap_{PROBLEM}.csv')
CONFIG_FILE_NAME = f'{PROBLEM}_{MODEL}.yaml'
CONFIG_FILE = os.path.join(BASE_PATH, CONFIG_FILE_NAME)

ERASE_DATASETS = True

VALUES = np.linspace(0,6,25)
C=3

DH = DataHandler(DATA_FILE)

def handle_data(data_dict):
    handled = {}
    handled.update({'loss': data_dict['test_loss']})
    handled.update({'accuracy': data_dict['test.metrics']['accuracy']})
    # handled.update({'f1': data_dict['test.metrics']['f1']})
    # handled.update({'recall': data_dict['test.metrics']['recall']})
    # handled.update({'precision': data_dict['test.metrics']['precision']})
    return handled

def prepare_dataset(config, value):
    p_inter = C-value/2
    p_outer = C+value/2
    config['data']['test']['problems'][PROBLEM]['p_inter'] = p_inter
    config['data']['test']['problems'][PROBLEM]['p_outer'] = p_outer
    test_dataset = get_test_dataset(config)
    return test_dataset

def step(path_to_chkpt):
    config = get_config(CONFIG_FILE)
    config['project'] = 'sweep'
    progress_bar = tqdm.tqdm(VALUES)
    for value in progress_bar:
        progress_bar.set_description(f'Value {value}.')
        pl_model = load_model(config, path_to_chkpt)
        setup_metric(pl_model, config)
        trainer = setup_trainer(config, pl_model)
        test_dataset = prepare_dataset(config, value)
        trainer.test(pl_model, test_dataloaders=test_dataset)
        wandb.finish()
        logged_metrics = trainer.logged_metrics
        clean_metrics = handle_data(logged_metrics)
        clean_metrics[VALUE_NAME] = value
        DH.add_entry(clean_metrics)


to_walk = os.walk(MODELS_DIR)
to_walk = [elt for elt in to_walk]
for dirpath, _, filenames in tqdm.tqdm(to_walk):
    for filename in filenames:
        path_to_file = os.path.join(dirpath, filename)
        step(path_to_chkpt=path_to_file)
        

        
