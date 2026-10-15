import re

content = open('c:/Users/1/Desktop/mini app/frontend/src/i18n/ru.ts', 'r', encoding='utf-8').read()

# Replace all keys by key name (mojibake-safe via regex on keys)
content = re.sub(
    r"'hunt\.targetMoreRegions': '[^']*'",
    "'hunt.targetMoreRegions': 'Найдите ещё {count} регион|региона|регионов'",
    content
)
content = re.sub(
    r"'goal\.moreRegions': '[^']*'",
    "'goal.moreRegions': 'Ещё {n} регион|региона|регионов в {country}'",
    content
)
content = re.sub(
    r"'hunt\.rollsCount': '[^']*'",
    "'hunt.rollsCount': 'ролл: {n}|ролла: {n}|роллов: {n}'",
    content
)
content = re.sub(
    r"'hunt\.bonusRolls': '[^']*'",
    "'hunt.bonusRolls': 'бонусный ролл|бонусных ролла|бонусных роллов'",
    content
)
content = re.sub(
    r"'roll\.many': '[^']*'",
    "'roll.many': 'ролл|ролла|роллов'",
    content
)

open('c:/Users/1/Desktop/mini app/frontend/src/i18n/ru.ts', 'w', encoding='utf-8').write(content)
print('Done')
