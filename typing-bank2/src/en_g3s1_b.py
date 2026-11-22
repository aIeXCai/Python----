# -*- coding: utf-8 -*-
"""三年级上册 英文 50 篇（第二部分：Unit 4–6 + 复习，26 篇）"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make_rows

R = make_rows(
    ed="2024 年 7 月第 1 版（ISBN 9787107382505）",
    st="人教PEP英语三年级上册（2024年版）目录",
    su="https://www.pep.com.cn/zslth/yyptypzj/xypep/3s/",
    lic="原创练习文（教材主题原创）；教材可免费在线阅读，但正文不转载",
)

ROWS = [
    # ---------- Unit 4 Plants around us ----------
    R(4, "Unit 4 Plants around us", "Unit 4 A Let's talk / B Let's talk", "The Sunflower", "narrative", [
        "I have a sunflower in my garden. It is very tall. It is taller than me.",
        "The sunflower has a big yellow head. The head turns to the sun. In the morning it looks east. In the evening it looks west.",
        "The sunflower gives me many seeds. I eat some. I keep some for next year. One plant can make many new plants.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 A Let's learn / B Let's learn", "Water and Sun", "narrative", [
        "A plant needs water. It needs sun, too. Without water, the leaves turn yellow.",
        "In summer, I water my plants every day. In winter, I water them only two times a week.",
        "My mother says, too much water is bad. The plant cannot drink it all. Its feet stay wet and it dies.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 A Let's spell / B Start to read", "Trees in My School", "narrative", [
        "There are many trees in my school. Some are tall. Some are small. They are in front of the building.",
        "In spring, the trees are green. In autumn, their leaves fall down. We sweep them into a big pile.",
        "In summer, we sit under the trees. The shade is cool. Trees make our school a nice place.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 单元综合", "Seeds", "narrative", [
        "A seed is very small. But a big tree can grow from a small seed. How does it happen?",
        "The seed needs warm soil and water. It opens. A little root goes down. A little green shoot goes up.",
        "After some days, you can see two small leaves. After some years, you can stand under the tree.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 单元综合", "Green Leaves", "narrative", [
        "Leaves are green. They catch light from the sun. They make food for the plant.",
        "Some leaves are big and round. Some are long and thin. Some have a nice smell.",
        "In autumn, many leaves change colour. Then they fall. But the tree is not dead. In spring it grows new ones.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 单元综合", "The Garden", "narrative", [
        "My grandma has a small garden behind her house. She grows tomatoes and beans there.",
        "Every morning she goes out with a small bucket. She waters the plants and looks at the leaves.",
        "In summer, we pick tomatoes together. They are red and sweet. Grandma says, Fresh food tastes best.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 文化拓展", "A Plant I Grow", "narrative", [
        "I grow a small plant in a pot. It is a cactus. I keep it on my desk.",
        "A cactus does not need much water. It likes dry soil and bright light. It has small sharp points.",
        "It grows very slowly. But every year it is a little taller. I am patient with it.",
        "Next year it will be taller than me.",
    ]),
    R(4, "Unit 4 Plants around us", "Unit 4 文化拓展", "Flowers in Spring", "narrative", [
        "In spring, many flowers come out. Some are white. Some are pink. Some are purple.",
        "The park near my home is full of flowers. Bees fly from flower to flower. They take something sweet.",
        "We must not pick the flowers. Everyone wants to see them. If you love a flower, let it stay on the plant.",
    ]),
    # ---------- Unit 5 The colourful world ----------
    R(5, "Unit 5 The colourful world", "Unit 5 A Let's talk / B Let's talk", "Colours Around Me", "narrative", [
        "My world is full of colours. The sky is blue. The grass is green. The sun is yellow.",
        "My school bag is red. My shoes are white. My pencil box is orange.",
        "I like blue best. It makes me feel calm. What colour do you like?",
        "My friend likes yellow. Her bag is yellow. Her shoes are yellow too. She is always happy.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 A Let's learn / B Let's learn", "My Red Bag", "narrative", [
        "I have a red bag. I use it every day. It is not big, but it is strong.",
        "In my bag, I have books, a pencil box and a water bottle. There is a small green frog on the front.",
        "My friend has a blue bag. We put them on the same chair. The red one and the blue one look nice together.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 A Let's spell / B Start to read", "The Rainbow", "narrative", [
        "After the rain, the sun comes out. Sometimes we can see a rainbow in the sky.",
        "A rainbow has many colours. First red, then orange, yellow, green, blue and purple.",
        "A rainbow does not stay long. It goes away in a few minutes. So look up quickly when it appears.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 单元综合", "Blue and Green", "narrative", [
        "Blue and green are cool colours. The sea is blue. The forest is green.",
        "Red and yellow are warm colours. Fire is red. The sun is yellow.",
        "Artists use warm colours for happy things. They use cool colours for quiet things. Colour can tell a feeling.",
        "Red is warm. Blue is cool. I like both.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 单元综合", "Colours in the Market", "narrative", [
        "The market near my home is very colourful. Tomatoes are red. Cucumbers are green. Lemons are yellow.",
        "My mother buys vegetables there. She picks the red tomatoes and the green beans.",
        "I like the fruit table best. Purple grapes, orange oranges and red apples. It looks like a picture.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 单元综合", "What Colour Is It?", "dialogue", [
        "Look at this bird. What colour is it? It is small and grey. Its beak is yellow.",
        "Look at that car. What colour is it? It is white. Its windows are black.",
        "Now look at my hand. What colour is my pencil? It is green. Please give it to me.",
        "My bag is blue. My ruler is white. My book is yellow.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 文化拓展", "Painting a Picture", "narrative", [
        "On Sunday, I paint a picture. I use a big brush and six colours.",
        "I paint a blue river at the bottom. I paint a green hill behind it. The sky is light blue.",
        "My little brother paints a big purple sun. It is funny, but I like it. Everyone sees the world in a different way.",
    ]),
    R(5, "Unit 5 The colourful world", "Unit 5 文化拓展", "Night Colours", "narrative", [
        "At night, the world is not only black. The moon is white and yellow.",
        "Some lights are orange. Some are green. The stars are small and white.",
        "When I turn off my light, I can see a little red light from my clock. It stays with me all night.",
        "Red is small and warm. The room is big and dark. It is like a little friend.",
    ]),
    # ---------- Unit 6 Useful numbers ----------
    R(6, "Unit 6 Useful numbers", "Unit 6 A Let's talk / B Let's talk", "Numbers in My Class", "narrative", [
        "How many students are in my class? There are forty. Twenty-one boys and nineteen girls.",
        "We have six classes every day. Each class is forty minutes long.",
        "Our classroom is on the second floor. Room number is 302. I can find it easily.",
        "There are forty-two students in my class. Twenty-two are boys. Twenty are girls.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 A Let's learn / B Let's learn", "Counting Apples", "narrative", [
        "My mother buys a bag of apples. There are twelve in the bag. She asks me to count them.",
        "I take them out one by one. One, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve.",
        "We eat two. Now there are ten. Tomorrow we eat two more. How many are left?",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 A Let's spell / B Start to read", "My Phone Number", "narrative", [
        "Every child should know three numbers. One is one-one-nine. One is one-two-zero. One is one-one-zero.",
        "Those numbers help people in danger. We must not call them for fun.",
        "I also know my father's phone number. I can say it quickly. This is important when I need help.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 单元综合", "How Many?", "dialogue", [
        "How many books are on the desk? There are five. Two are mine and three are yours.",
        "How many windows are in this room? There are three. One is open.",
        "How many pencils do you have? I have six. But I can only find four. Where are the other two?",
        "Oh, they are in my desk. One, two. Here you are.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 单元综合", "Numbers at Home", "narrative", [
        "Numbers are everywhere at home. Our flat is on the fifth floor. The door number is 501.",
        "The clock says seven. It is time to get up. At eight, we have breakfast.",
        "My grandmother says, we use numbers every day. She is right. I never think about it.",
        "The door number is 501. The bus is number twenty. The clock says seven.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 单元综合", "The Clock", "narrative", [
        "A clock tells us the time. It has numbers from one to twelve on its face.",
        "The short hand shows the hour. The long hand shows the minute. When both hands are at twelve, it is twelve o'clock.",
        "I look at the clock in the morning. I look at it again after school. A clock helps me not be late.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 文化拓展", "Buying Snacks", "narrative", [
        "I have ten yuan. I go to the small shop near my school.",
        "A packet of biscuits is four yuan. A bottle of water is two yuan. I want both.",
        "I give the shopkeeper ten yuan. She gives me four yuan back. I say thank you and go home.",
        "The snacks are two yuan. I have eight yuan now. I can buy one more thing.",
    ]),
    R(6, "Unit 6 Useful numbers", "Unit 6 文化拓展", "Number Games", "narrative", [
        "We play a number game in class. One student says one. The next says two. Then three and four.",
        "When the number has a seven in it, you must clap. Not say it. If you say it, you are out.",
        "At first we make many mistakes. Everyone laughs. After a few times, we can go to fifty.",
    ]),
    # ---------- 复习 ----------
    R(0, "Review 复习", "Unit 1–Unit 3 复习", "Our English Class", "narrative", [
        "We have English class three times a week. Our teacher is Miss Wang. She is kind.",
        "In class, we learn new words. We read them and write them. We also sing English songs.",
        "I like the story time best. Miss Wang tells a short story. We listen carefully and answer her questions.",
    ]),
    R(0, "Review 复习", "Unit 4–Unit 6 复习", "A Happy Day", "narrative", [
        "Today is Friday. I am happy because it is a good day.",
        "In the morning, I count the trees in the park. There are eight. In the afternoon, I water my sunflower.",
        "I see a rainbow after the rain. It has seven colours. I go home and tell my mother everything.",
    ]),
]
