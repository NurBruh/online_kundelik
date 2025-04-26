from django import template
from collections import defaultdict

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Шаблонда сөздіктен элемент алу үшін фильтр."""
    return dictionary.get(key)

@register.simple_tag
def is_correct_answer(answer, correct_choice_ids, selected_choices_map):
    """
    Берілген жауаптың дұрыстығын тексереді.
    - answer: Answer объектісі
    - correct_choice_ids: assessment үшін барлық дұрыс Choice ID-лерінің жиыны (set)
    - selected_choices_map: MAQ үшін {question_pk: {choice_pk1, choice_pk2}} форматындағы сөздік
    """
    question = answer.question
    is_correct = False

    if question.question_type in ['MCQ', 'TF']:
        # Бір таңдау: егер таңдалған нұсқа бар және ол дұрыс болса
        if answer.selected_choice and answer.selected_choice.pk in correct_choice_ids:
            is_correct = True
    elif question.question_type == 'MAQ':
        # Көп таңдау: егер барлық дұрыс нұсқалар таңдалып, қате нұсқалар таңдалмаса
        correct_choices_for_q = set(c.pk for c in question.choices.filter(is_correct=True))
        selected_choices_for_q = selected_choices_map.get(question.pk, set())

        # Таңдалған нұсқалар жиыны дұрыс нұсқалар жиынымен дәл келсе
        if correct_choices_for_q == selected_choices_for_q and correct_choices_for_q: # Бос жиын болмауы керек
            is_correct = True
    # OPEN сұрақтарын бұл жерде тексермейміз, олар қолмен бағаланады.

    return is_correct