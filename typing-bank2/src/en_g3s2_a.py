# -*- coding: utf-8 -*-
"""三年级下册 英文 50 篇（第一部分：Unit 1–3，24 篇）"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make_rows

R = make_rows(
    ed="2025 年春版（三年级起点）",
    st="人教PEP英语三年级下册（2025年春版）目录",
    su="https://www.pep.com.cn/zslth/yyptypzj/xypep/3x/",
    lic="原创练习文（教材主题原创）；教材可免费在线阅读，但正文不转载",
)

ROWS = [
    # ---------- Unit 1 Meeting new people ----------
    R(1, "Unit 1 Meeting new people", "Unit 1 A Let's talk / B Let's talk", "A New Classmate", "narrative", [
        "A new girl comes to our class today. Her name is Mei. She comes from a small town near the sea.",
        "She is a little shy. She sits in the last row and says nothing. At break, I go to her desk and say hello.",
        "She smiles and says hello back. I show her where the water is. Now she has a friend in this school.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 A Let's learn / B Let's learn", "This Is My Friend", "narrative", [
        "This is my friend. His name is Peter. He is ten years old. He is in Class Four.",
        "Peter is tall. He has short hair and a big smile. He likes football and orange juice.",
        "We meet in the playground every day. We walk home together after school. He lives near my house.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 A Let's spell / B Start to read", "Where Are You From?", "dialogue", [
        "Hello. My name is Anna. Where are you from?",
        "I am from China. I live in Guangzhou. And you? I am from Australia. My city is near the sea.",
        "Do you like it here? Yes, I do. The food is good and the people are kind. But I miss my dog.",
        "My dog is small and brown. I want to see him again.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 单元综合", "Nice to Meet You", "dialogue", [
        "Good morning. Are you the new student? Yes, I am. My name is Tom.",
        "Nice to meet you, Tom. I am Miss Li. Welcome to our class. Thank you, Miss Li.",
        "Please sit here. If you need help, ask me or ask your classmate. Okay. Thank you very much.",
        "I have two books and one ruler. Can I put them here?",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 单元综合", "My New Neighbour", "narrative", [
        "A new family moves into the flat next to ours. They have a boy of my age.",
        "His name is Ken. He has a bicycle. He asks me to ride with him in the park.",
        "We ride for an hour. My legs are tired but I am happy. Now I have a neighbour and a friend.",
        "Tomorrow we will ride again after school.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 单元综合", "At the Bus Stop", "narrative", [
        "I wait for the bus every morning. A boy waits there, too. He has a big blue bag.",
        "One day, the bus is late. We talk. He tells me he goes to the school near the park.",
        "Now we take the same bus every day. We talk about our homework and our teachers.",
        "The bus comes at seven. We are never late.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 文化拓展", "A Letter to a New Friend", "letter", [
        "Dear Lily, How are you? I am fine. I have a new friend at school. Her name is Lucy.",
        "Lucy is from Canada. She can sing very well. She teaches me an English song every week.",
        "I teach her a Chinese song, too. It is fun. Please write to me soon. Yours, Mei.",
    ]),
    R(1, "Unit 1 Meeting new people", "Unit 1 文化拓展", "Names and Nicknames", "narrative", [
        "My name is Zhang Wei. At home, my family calls me Weiwei. At school, my friends call me Wei.",
        "My English teacher gives me an English name. It is David. She says it is easy to say.",
        "Now some people call me David, some call me Wei. Both are me. I like both names.",
    ]),
    # ---------- Unit 2 Expressing yourself ----------
    R(2, "Unit 2 Expressing yourself", "Unit 2 A Let's talk / B Let's talk", "How Do You Feel?", "dialogue", [
        "You look sad today. What is the matter? I cannot find my pencil box.",
        "Do not worry. Let us look for it. Is it in your bag? No, it is not.",
        "Look under the desk. Oh! Here it is. Thank you. Now I feel happy again.",
        "My pen is lost. I look in my bag. Not here. I look on the floor. Not here.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 A Let's learn / B Let's learn", "I Am Happy Today", "narrative", [
        "Today is a good day. I am happy. The sun is out and the sky is blue.",
        "In the morning, I get a good mark in English. At lunch, my friend shares her cake with me.",
        "After school, my father takes me to the park. We play ball. I laugh a lot. I want this day to be long.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 A Let's spell / B Start to read", "When I Am Sad", "narrative", [
        "Sometimes I am sad. Maybe I lose a game. Maybe a friend does not talk to me.",
        "When I am sad, I do not want to play. I sit near the window and look outside.",
        "My mother comes and sits with me. She does not ask many questions. After a while, I feel better.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 单元综合", "My Favourite Thing", "narrative", [
        "My favourite thing is a small blue notebook. My mother gives it to me on my birthday.",
        "I write in it every night. I write what I do and how I feel. Some pages have small drawings.",
        "When I read the old pages, I remember many things. A notebook can keep your days for you.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 单元综合", "Saying Thank You", "narrative", [
        "Someone holds the door for me. I say thank you. Someone gives me a seat on the bus. I say thank you.",
        "These are small words. But they make people smile. My mother says, always say them.",
        "Yesterday a boy helped me pick up my books. I said thank you. He looked happy all morning.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 单元综合", "A Picture for Mum", "narrative", [
        "Tomorrow is Mother's Day. I want to give my mother something. I do not have money.",
        "So I draw a picture. In the picture, my mother and I are in the park. The sun is yellow and big.",
        "I write some words under it: I love you, Mum. When she sees it, she puts it on the wall.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 文化拓展", "I Don't Like It", "dialogue", [
        "Do you like carrots? No, I do not. I do not like the taste.",
        "But carrots are good for you. I know. I eat them, but I do not like them.",
        "That is fine. We do not have to like everything. I do not like milk, but I drink it.",
        "My sister does not like eggs. She eats rice and vegetables. That is fine too.",
    ]),
    R(2, "Unit 2 Expressing yourself", "Unit 2 文化拓展", "Tell Me Your Dream", "narrative", [
        "My teacher asks us about our dreams. She says, what do you want to be?",
        "I want to be a doctor. I want to help sick people. My friend wants to be a cook.",
        "Another friend wants to be a bus driver. He says he likes to take people to many places.",
        "I want to be a teacher. I like to help small children read.",
    ]),
    # ---------- Unit 3 Learning better ----------
    R(3, "Unit 3 Learning better", "Unit 3 A Let's talk / B Let's talk", "How I Learn English", "narrative", [
        "I learn English in three ways. First, I read the new words every morning.",
        "Second, I listen to English songs. I do not know every word, but I like the sound.",
        "Third, I talk with my friend. We make short dialogues. We laugh when we make mistakes.",
        "Fourth, I watch English cartoons. I do not understand every word, but I like the songs.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 A Let's learn / B Let's learn", "My Study Corner", "narrative", [
        "I have a small desk near the window. This is my study corner.",
        "On the desk, there is a lamp, some books and a cup of pencils. The wall has a map of China.",
        "I do my homework here every evening. When I finish, I turn off the lamp and feel good.",
        "There is a small plant on my desk. It is green. It likes the light from the window.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 A Let's spell / B Start to read", "Asking the Teacher", "dialogue", [
        "Miss Wang, may I ask a question? Yes, please.",
        "I do not understand this word. Can you say it again? Of course. Listen carefully: beauti-ful.",
        "Thank you. Now I understand. Good. Never be afraid to ask.",
        "I do not know this word. Can you help me? Yes. Look at the picture first. Oh, I see. It is a kite.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 单元综合", "Reading Together", "narrative", [
        "Every Friday, we read a story in class. The teacher reads the first page, then we read together.",
        "Some words are new. We write them on the board. We guess what they mean from the picture.",
        "At the end, the teacher asks, what happened in the story? Many hands go up.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 单元综合", "A Mistake I Made", "narrative", [
        "Last week, I wrote 'I have a orange' in my exercise book. My teacher put a red mark.",
        "She said, we say 'an orange'. I felt a little silly. But I remembered it after that.",
        "Now I say 'an apple' and 'an orange'. A mistake can help you learn.",
        "Yesterday I said 'a egg'. My friend laughed. Now I say 'an egg'. I do not forget it now.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 单元综合", "Practice Every Day", "narrative", [
        "My father says, ten minutes a day is better than one hour a week.",
        "So I practise English for ten minutes every evening. I read two pages and say the words aloud.",
        "At first, it felt slow. After a month, I could read faster. Now it is easy to do.",
        "I read ten minutes every night. Ten minutes is not long. But ten minutes every day is a lot.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 文化拓展", "My Favourite Subject", "narrative", [
        "My favourite subject is science. I like to ask why. Why is the sky blue? Why do leaves fall?",
        "In science class, we do small experiments. We put a seed in the soil and watch it grow.",
        "Some answers are hard. But I like the questions more than the answers.",
    ]),
    R(3, "Unit 3 Learning better", "Unit 3 文化拓展", "Learning with a Friend", "narrative", [
        "Amy and I study together twice a week. We sit at my desk and open our books.",
        "She reads English, I read Chinese. When one of us does not know a word, the other helps.",
        "Sometimes we talk too much and do not finish. But we always come back the next day.",
        "Two people can learn more than one. That is why we sit together.",
    ]),
]
