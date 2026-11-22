# -*- coding: utf-8 -*-
"""三年级上册 英文 50 篇（第一部分：Unit 1–3，24 篇）"""

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
    # ---------- Unit 1 Making friends ----------
    R(1, "Unit 1 Making friends", "Unit 1 A Let's talk / B Let's talk", "My New Friend", "narrative", [
        "Hello! My name is Lily. I am nine years old. I am in Class Two, Grade Three. I am new here.",
        "This is Tom. He is my new friend. He is nine, too. He likes blue. I like green. We sit together in the classroom.",
        "We say hello in the morning. We play together at break. We share our books and pencils. School is happy with a friend.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 A Let's learn / B Let's learn", "In the Classroom", "narrative", [
        "This is my classroom. It is big and bright. There are many desks and chairs. There is a blackboard on the wall.",
        "Miss Wang is my English teacher. She says hello to us every morning. We say hello back. We sing an English song together.",
        "My desk is near the window. I can see a tree outside. At break, I talk with Amy. We are good friends.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 A Let's spell / B Start to read", "Hello and Goodbye", "narrative", [
        "In the morning, I meet my friend at the school gate. I say, Good morning! He says, Good morning! Then we walk in together.",
        "After class, we say goodbye. I say, See you tomorrow! He waves his hand and says, See you!",
        "My little sister is three. She can say hello and goodbye now. She says them to everyone. Everyone smiles at her.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 单元综合", "A New Boy", "narrative", [
        "A new boy comes to our class today. His name is Sam. He is from Canada. He speaks English and a little Chinese.",
        "He sits next to me. He does not know our games. I show him how to play. He learns fast.",
        "At lunch, we eat together. He gives me an apple. I give him a cake. Now he is not new. He is my friend.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 单元综合", "Playing Together", "narrative", [
        "At break, we play in the playground. Some boys run. Some girls skip. I play ball with Tom.",
        "Tom throws the ball. I catch it. Then I throw it back. We laugh a lot.",
        "A girl falls down. We stop and help her up. She says thank you. We say, That is all right. Then we play again.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 单元综合", "My Best Friend", "narrative", [
        "My best friend is Amy. She is nine years old. She has long black hair and a big smile.",
        "Amy likes to draw. She draws cats, birds and flowers. She gives me a picture of a cat. I put it on my desk.",
        "We are in the same class. We go home together every day. We talk about many things. A good friend listens to you.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 文化拓展", "Names and Countries", "narrative", [
        "My name is Li Ming. I am from China. I live in Guangzhou. It is a big city in the south.",
        "My friend Emma is from England. She says her city is small but very old. She shows me a photo of it.",
        "We are from different countries. But we like the same things. We both like music and ice cream.",
    ]),
    R(1, "Unit 1 Making friends", "Unit 1 文化拓展", "At the School Gate", "narrative", [
        "Every morning, many people are at the school gate. Children come with their bags. Parents say goodbye.",
        "I see my friend Ben. He is eating bread. He gives me a piece. We walk to the classroom together.",
        "The bell rings at eight. We run to our seats. The teacher comes in. Our day begins.",
    ]),
    # ---------- Unit 2 Different families ----------
    R(2, "Unit 2 Different families", "Unit 2 A Let's talk / B Let's talk", "My Family Photo", "narrative", [
        "This is a photo of my family. There are five people in it. My father, my mother, my sister, my brother and me.",
        "My father is tall. He works in a hospital. My mother is a teacher. She teaches Chinese.",
        "My sister is six. My brother is two. He is very small. We take this photo in the park in spring.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 A Let's learn / B Let's learn", "Grandma and Grandpa", "narrative", [
        "My grandma and grandpa live in a small town. There are many trees near their house.",
        "Grandma makes good dumplings. Grandpa likes to walk in the morning. He takes me with him.",
        "We visit them every month. I like their house. It is quiet and warm. Grandma always gives me something to eat.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 A Let's spell / B Start to read", "My Cousin", "narrative", [
        "I have a cousin. His name is Peter. He is eight years old. He lives in another city.",
        "Peter likes football. He plays every day after school. He can run very fast.",
        "In summer, he comes to my home. We play in the park. We eat ice cream together. I wish he lived near me.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 单元综合", "A Big Family", "narrative", [
        "My friend Anna has a big family. She has two sisters and one brother. They live in a big house.",
        "Every evening, they have dinner together. The table is full of food. Everyone talks and laughs.",
        "Anna says her house is noisy. But she likes it. When the house is quiet, she feels something is missing.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 单元综合", "Helping at Home", "narrative", [
        "At home, I help my mother. I put my toys in the box. I water the small plant on the window.",
        "My sister helps too. She puts the bowls on the table. She is only six, but she is careful.",
        "My father washes the dishes. After that, we sit together. We talk about our day. This is my favourite time.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 单元综合", "Who Is This?", "narrative", [
        "Look at this photo. Who is this man? He is my uncle. He has a big dog.",
        "Who is this woman? She is my aunt. She is my mother's sister. She lives in Shanghai.",
        "And who is this little girl? That is me! I am four years old in this photo. My hair is very short.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 文化拓展", "Dinner Together", "narrative", [
        "In my family, dinner is at six. We sit around one table. My mother puts rice and fish in the middle.",
        "My father asks, How was your day? We all answer. My brother talks about his game. I talk about my class.",
        "After dinner, we clean the table. Then we watch TV for a short time. Every family has its own way.",
    ]),
    R(2, "Unit 2 Different families", "Unit 2 文化拓展", "Family Tree", "narrative", [
        "Our teacher asks us to draw a family tree. She gives us a big piece of paper.",
        "I draw my grandma and grandpa at the top. Under them, I draw my father and my mother. Then I draw me.",
        "My tree is small. My friend Ben's tree is very big. He has many aunts and uncles. Every family is different.",
    ]),
    # ---------- Unit 3 Amazing animals ----------
    R(3, "Unit 3 Amazing animals", "Unit 3 A Let's talk / B Let's talk", "My Cat", "narrative", [
        "I have a cat. Her name is Mimi. She is white and grey. She has two big eyes.",
        "Mimi likes to sleep in the day. At night, she walks around the house. She can see in the dark.",
        "When I come home, Mimi runs to me. She puts her head on my leg. I think she is saying hello.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 A Let's learn / B Let's learn", "At the Zoo", "narrative", [
        "On Sunday, we go to the zoo. There are many animals. I see lions, monkeys and elephants.",
        "The elephant is very big. It has a long nose. It uses the nose to drink water and to pick up food.",
        "The monkeys are funny. They jump from tree to tree. One monkey takes a banana from a boy. Everyone laughs.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 A Let's spell / B Start to read", "A Bird in the Tree", "narrative", [
        "There is a bird in the tree near my window. It is small and brown. It sings every morning.",
        "The bird makes a nest with small sticks and grass. It puts the nest in a safe place.",
        "One day, I see three baby birds in the nest. They are very small. Their mouths are wide open. The mother brings food.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 单元综合", "Big and Small", "narrative", [
        "Some animals are very big. The blue whale is the biggest animal in the sea. It is longer than a bus.",
        "Some animals are very small. An ant is smaller than your finger. But an ant can carry a heavy thing.",
        "Big or small, every animal has its own way to live. That is why the world is interesting.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 单元综合", "The Panda", "narrative", [
        "The panda is a lovely animal. It is black and white. It has a round face and small ears.",
        "Pandas live in the mountains of China. They eat bamboo for many hours every day.",
        "Baby pandas are very small when they are born. They drink milk from their mother. Many people love pandas.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 单元综合", "Animals in the Sea", "narrative", [
        "The sea is full of animals. Some are fish. Some are not. A dolphin is not a fish. It needs air.",
        "A dolphin can swim fast. It can jump out of the water. It makes sounds under the water.",
        "A crab walks on the sand. It has ten legs. When you come near, it runs away very fast.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 文化拓展", "My Dog Can Run", "narrative", [
        "My dog is called Lucky. He is brown. He is two years old. He is bigger than my cat.",
        "Lucky can run very fast. He can catch a ball in the air. He can also swim in the river.",
        "Every evening, I take him out. He runs and I walk. When we come home, he sleeps at my feet.",
    ]),
    R(3, "Unit 3 Amazing animals", "Unit 3 文化拓展", "A Visit to the Farm", "narrative", [
        "My uncle has a farm. There are cows, ducks and hens on it. The farm is outside the city.",
        "In the morning, the hens make a lot of noise. The ducks walk to the water. The cows eat grass slowly.",
        "I help my uncle. I give food to the hens. I carry water. At night, I am tired but happy.",
    ]),
]
