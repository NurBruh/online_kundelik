# kundelik/templatetags/dict_filters.py
from django import template

register = template.Library()

@register.filter(name='get')
def get_dict_item(dictionary, key):
    """
    Пользовательский фильтр шаблона для получения элемента из словаря по ключу.
    Использование: {{ my_dictionary|get:my_key }}
    Возвращает None, если ключ не найден или входные данные не являются словарем.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None # Или вернуть пустую строку '', или вызвать ошибку, в зависимости от желаемого поведения