import pandas as pd

df = pd.read_csv('tickets.csv')

def is_nan(col):
    if col != col:
        return False
def engineer(col):
     if col == "":
          return False
def opened(col):
     if col is {"%d%m%y %h%m"}:
          return False
def status(col):
     if col == "Open" or col == "Assigned" or col == "Resolved" or col == "Closed":
          return False 
def tier(col):
     if float(col) <= 3 and float(col)>= 1:
          return False
def whole_number(col):
    is_nan(col)
    return isinstance(col, int)

for id, row in df.iterrows():
    for id, col in row.items():
        
        if id == "id":
            
            if whole_number(col):
                pass 
            elif tier(col):
                pass
            elif status(col):
                pass    
            elif opened(col):
                pass
            elif engineer(col):
                pass
            elif opened(col):
                pass
            else:
                break