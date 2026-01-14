from datasets import load_dataset

dataset = load_dataset("jcblaise/fake_news_filipino")

# View a sample
print(dataset['train'][0])
# Output: {'label': 0, 'article': '...text...'} (0 usually = Fake, 1 = Real, check documentation)