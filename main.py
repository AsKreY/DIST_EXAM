import hashlib  # всё ясно без слов
import os  # opening pdfs
import sqlite3  # DB
import tkinter as tk  # GUI
from abc import ABCMeta  # Abstractions
from random import choice, sample  # random examiners and questions
from time import sleep
from tkinter import filedialog, ttk, Tk  # GUI
from tkinter.messagebox import showerror, showinfo  # GUI
from uuid import uuid4  # id

from fpdf import FPDF  # creating pdfs


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class ExamDatabase(metaclass=Singleton):
    def __init__(self):
        self.db = sqlite3.connect("server.db")
        self.sql = self.db.cursor()

        self.sql.execute("""CREATE TABLE IF NOT EXISTS exam_db(student_id 
        int, examiner_id int, subject text, expected_grade int, grade int, 
        retake_nums int 
        DEFAULT 0, work_id int)""")

        self.sql.execute("""CREATE TABLE if NOT EXISTS students(
        student_name text, student_login text, password_hash int, 
        student_id int)""")

        self.sql.execute("""CREATE TABLE if NOT EXISTS examiners(
        examiner_name text, examiner_login text, password_hash int, 
        examiners_department text, 
        examiners_id int)""")

        self.sql.execute("""CREATE TABLE if NOT EXISTS subject_department(
        subject text, department text)""")

        self.sql.execute("""CREATE TABLE if NOT EXISTS exam_questions(
                examiner_id int, subject text, mark int, question text)""")

    def __del__(self):
        self.db.close()


class Person(metaclass=ABCMeta):
    def __init__(self, input_id):
        self._db_access = ExamDatabase()
        self._id = input_id


class Student(Person):
    def get_grade_reg_info(self):
        self._db_access.sql.execute(
            "SELECT * FROM exam_db WHERE "
            "student_id=:input_id",
            {"input_id": self._id})
        return [(subject, grade, num_of_retakes) for ID,
                                                     examiner,
                                                     subject,
                                                     expected_grade,
                                                     grade,
                                                     num_of_retakes,
                                                     work_id
                in self._db_access.sql.fetchall()]

    def reg_to_exam(self, subject, expected_grade):
        self._db_access.sql.execute("SELECT retake_nums FROM exam_db WHERE "
                                    "student_id=:self_id AND "
                                    "subject=:subject_inp",
                                    {"self_id": self._id,
                                     "subject_inp": subject})
        tmp = self._db_access.sql.fetchall()
        num_of_retakes = 0 if len(tmp) == 0 else (tmp[0][0] + 1)
        if num_of_retakes != 0:
            if num_of_retakes > 2:
                showerror("Error", "Too many retakes")
                return -1
            self._db_access.sql.execute("SELECT grade FROM exam_db WHERE"
                                        "student_id=:self_id AND "
                                        "subject=:subject_inp",
                                        {"self_id": self._id,
                                         "subject_inp": subject})
            if self._db_access.sql.fetchall()[0] > 2:
                showerror("Error", "Exam has already been passed")
                return -1
            self._db_access.sql.execute("DELETE FROM exam_db WHERE "
                                        "student_id=:self_id AND "
                                        "subject=:subject_inp",
                                        {"self_id": self._id,
                                         "subject_inp": subject})
        self._db_access.sql.execute(
            "SELECT department "
            "FROM subject_department "
            "WHERE subject=:subject_inp",
            {"subject_inp": subject})
        subj_department = self._db_access.sql.fetchall()[0][0]
        self._db_access.sql.execute("SELECT * FROM examiners WHERE "
                                    "examiners_department=:subj_dep",
                                    {"subj_dep": subj_department})
        examiner = choice(self._db_access.sql.fetchall())
        self._db_access.sql.execute(
            "INSERT INTO exam_db (student_id, subject, retake_nums, "
            "expected_grade, examiner_id) values(?, ?, ?, ?, ?)",
            (self._id, subject, num_of_retakes, expected_grade, examiner[4]))
        self._db_access.db.commit()

        return examiner[4]

    def get_questions(self, subject: str, expected_grade: int, examiner_id:
                      int) -> list:
        """
        :param subject:
        :param expected_grade:
        :param examiner_id:
        :return: 
        """
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=15)
        self._db_access.sql.execute("SELECT question FROM exam_questions "
                                    "WHERE examiner_id={} AND "
                                    "subject=:subject_inp AND "
                                    "mark=:mark_inp".format(examiner_id),
                                    {"subject_inp": subject,
                                     "mark_inp": expected_grade})
        question_list = sample(self._db_access.sql.fetchall(), 3)

        for i in range(1, 4):
            pdf.cell(200, 10, txt="{}. {}".format(i, question_list[i - 1][0]),
                     ln=i, align='L')

        filename = filedialog.asksaveasfilename(filetypes=[("pdf files",
                                                            "*.pdf")])
        pdf.output(filename)
        os.system("xdg-open {}".format(filename))
        sleep(1)  # So now file may be opened

        os.remove(filename)

        return question_list

    def create_answer_file(self, questions: list, answers: list) -> int:
        """ Create pdf with answers

        :param questions:
        :param answers:
        :return: filename to work
        """
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
        pdf.set_font('DejaVu', '', 14)

        for i in range(1, 4):
            pdf.cell(200, 10, txt="{}. {}".format(i, questions[i - 1][0]),
                     ln=i, align='L')
            pdf.cell(200, 10, txt="Ответ: {}".format(answers[i - 1]), ln=i,
                     align='L')

        filename = int(uuid4()) % (10 ** 9 + 7)
        pdf.output("works/{}.pdf".format(filename))
        return filename


class Examiner(Person):
    def add_question(self, subject: str, mark: int, question: str) -> None:
        self._db_access.sql.execute(
            "INSERT INTO exam_questions VALUES (?, ?, "
            "?, ?)", (self._id, subject, mark, question))
        self._db_access.db.commit()

    def is_unchecked_works(self):
        self._db_access.sql.execute("SELECT work_id FROM exam_db WHERE "
                                    "examiner_id=:id_inp AND grade is null",
                                    {"id_inp":
                                         self._id})

        work_ids = self._db_access.sql.fetchall()
        return work_ids

    def check_work(self, work_id: int, mark: int):
        if 1 <= mark <= 10:
            if mark <= 2:
                self._db_access.sql.execute("UPDATE exam_db SET grade=:smth"
                                            "WHERE work_id=:smth_work",
                                            {"smth": mark,
                                             "smth_work": work_id})
            else:
                self._db_access.sql.execute("UPDATE exam_db SET grade=:smth, "
                                            "retake_nums = retake_nums + 1"
                                            "WHERE work_id=:smth_work",
                                            {"smth": mark,
                                             "smth_work": work_id})
            self._db_access.db.commit()
        else:
            showerror("Error", "Incorrect mark")

def enter_system(login: str, password: str, user_type: int, db_cursor:
                 sqlite3.Cursor) -> int:
    """
    :param db_cursor: cursor of DB
    :param login: user_login
    :param password: user_password
    :param user_type: 0 -- student, 1 -- examiner
    :return: id of Person
    :raise ValueError if there in no such person
    """
    if user_type == 0:
        db_cursor.execute("SELECT student_id FROM students WHERE "
                          "student_login=:login_inp AND "
                          "password_hash=:password_inp",
                          {"login_inp": login,
                           "password_inp": int.from_bytes(
                               hashlib.pbkdf2_hmac(
                                   'sha256',
                                   password.encode(
                                       'utf-8'),
                                   "".encode(
                                       'utf-8'),
                                   100000,
                                   dklen=128),
                               byteorder='big') % (
                                                   10 ** 9 + 7)})
    else:
        db_cursor.execute("SELECT examiners_id FROM examiners WHERE "
                          "examiner_login=:login_inp AND "
                          "password_hash=:password_inp",
                          {"login_inp": login,
                           "password_inp": int.from_bytes(
                               hashlib.pbkdf2_hmac(
                                   'sha256',
                                   password.encode(
                                       'utf-8'),
                                   "".encode(
                                       'utf-8'),
                                   100000,
                                   dklen=128),
                               byteorder='big') % (
                                                   10 ** 9 + 7)})

    found_id = db_cursor.fetchall()

    if len(found_id) == 0:
        raise ValueError("There is no such person")

    return found_id[0]


def reg_student(name: str, login: str, password: str, db_cursor:
                sqlite3.Cursor) -> int:
    """ Creates new student user and give his id
    :param db_cursor: cursor of DB
    :param name: 
    :param login: 
    :param password: 
    :return: id of new user
    :raises: ValueError if there is already such login
    """
    db_cursor.execute("SELECT * FROM students WHERE student_login=:login_inp",
                      {"login_inp": login})

    if len(db_cursor.fetchall()) != 0:
        raise ValueError("There is user with this login")

    created_id = int(uuid4()) % (10 ** 9 + 7)
    db_cursor.execute("INSERT INTO students VALUES(?, ?, ?, ?)",
                      (name, login,
                       int.from_bytes(hashlib.pbkdf2_hmac('sha256',
                                                          password.
                                                          encode('utf-8'),
                                                          "".encode('utf-8'),
                                                          100000,
                                                          dklen=128),
                                                          byteorder='big') %
                                                          (10 ** 9 + 7),
                                                          created_id))
    db_cursor.connection.commit()
    return created_id


def answers_input():
    answers = []

    def send():
        answers.append(text_one.get("1.0", "end-1c"))
        answers.append(text_two.get("1.0", "end-1c"))
        answers.append(text_three.get("1.0", "end-1c"))
        ans_win.destroy()

    ans_win = Tk()
    ans_win.maxsize(width=805, height=925)
    ans_win.minsize(width=805, height=925)
    ans_win.title("Ввод ответов")

    lbl_one = ttk.Label(ans_win, text="First question :")
    lbl_one.place(x=0, y=0)

    lbl_two = ttk.Label(ans_win, text="Second question :")
    lbl_two.place(x=0, y=300)

    lbl_three = ttk.Label(ans_win, text="Third question :")
    lbl_three.place(x=0, y=600)

    text_one = tk.Text(ans_win, height=16, width=100)
    text_one.place(x=0, y=25)

    text_two = tk.Text(ans_win, height=16, width=100)
    text_two.place(x=0, y=325)

    text_three = tk.Text(ans_win, height=16, width=100)
    text_three.place(x=0, y=625)

    submit_btn = ttk.Button(ans_win, text="Отправить", command=send)
    submit_btn.place(x=0, y=900)

    ans_win.mainloop()
    return answers


def student_ui(st_id: int):
    student = Student(st_id)

    def grade_showing():
        a = student.get_grade_reg_info()
        result = ""
        if len(a) == 0:
            result = "Записи об экзаменах отсутствуют"
        else:
            for note in a:
                result += "Экз:{}, Оц:{}, Чп:{}\n".format(note[0], note[1],
                                                          note[2])
        showinfo("Экзамены", result)

    def exam_reg_ui():
        def ex_reg():
            if grade.get() == "" or subject.get() == "":
                showerror("Error", "Введите данные")
            else:
                expected_grade = grade.get()
                if expected_grade <= 4:
                    expected_grade = 4
                elif expected_grade <= 7:
                    expected_grade = 7
                else:
                    expected_grade = 10

                examiners_id = student.reg_to_exam(subject.get(),
                                                   expected_grade)
                if examiners_id == -1:
                    return
                questions = student.get_questions(subject.get(),
                                                  expected_grade,
                                                  examiners_id)

                answers = answers_input()

                student.create_answer_file(questions, answers)

                exam_reg_win.destroy()

        exam_reg_win = Tk()
        exam_reg_win.title("Регистрация на экзамен")
        exam_reg_win.maxsize(width=500, height=400)
        exam_reg_win.minsize(width=500, height=400)

        subject_lbl = ttk.Label(exam_reg_win, text="Экзамен :",
                                font='Verdana 10 bold')
        subject_lbl.place(x=0, y=0)

        grade_lbl = ttk.Label(exam_reg_win, text="Желаемая оценка :",
                              font='Verdana 10 bold')
        grade_lbl.place(x=0, y=30)

        subject = tk.StringVar()
        grade = tk.IntVar()

        subject_ent = ttk.Entry(exam_reg_win, width=40,
                                textvariable=subject)
        subject_ent.focus()
        subject_ent.place(x=180, y=0)

        grade_ent = ttk.Entry(exam_reg_win, width=30, textvariable=grade)
        grade_ent.place(x=180, y=33)

        sign_up_btn = ttk.Button(exam_reg_win, text="Зарегистрироваться",
                                 command=ex_reg)
        sign_up_btn.place(x=0, y=70)

        exam_reg_win.mainloop()

    win = Tk()
    win.title("СДСЭ студент")
    win.maxsize(width=500, height=400)
    win.minsize(width=500, height=400)

    btn_grade = ttk.Button(win, text="Информация об экзаменах",
                           command=grade_showing)
    btn_grade.place(x=0, y=0)
    btn_reg = ttk.Button(win, text="Начать экзамен", command=exam_reg_ui)
    btn_reg.place(x=0, y=30)

    win.mainloop()


def examiner_ui(ex_id: int):
    examiner = Examiner(ex_id)

    def que_add():
        # TODO: why label arent read??????
        def send():
            if mark.get() == "" or subject.get() == "" or que_txt.get("1.0",
                                                                      "end-1c") \
                    == "":
                showerror("Error", "Введите все аргументы")
            else:
                try:
                    tr_mark = mark.get()
                    if tr_mark <= 4:
                        tr_mark = 4
                    elif tr_mark <= 7:
                        tr_mark = 7
                    else:
                        tr_mark = 10
                    examiner.add_question(subject.get(), tr_mark, que_txt.get(
                        "1.0", "end-1c"))
                except Exception:
                    showerror("Error", "Что-то пошло не так")
            que_win.destroy()

        que_win = Tk()
        que_win.title("Добавление вопроса")
        que_win.minsize(height=400, width=500)
        que_win.maxsize(height=400, width=500)

        sub_lbl = ttk.Label(que_win, text="Введите предмет :")
        sub_lbl.place(x=0, y=0)

        mark_lbl = ttk.Label(que_win, text="Введите оценку :")
        mark_lbl.place(x=0, y=30)

        que_lbl = ttk.Label(que_win, text="Введите вопрос :")
        que_lbl.place(x=0, y=60)

        subject = tk.StringVar()
        mark = tk.IntVar()

        subject_ent = ttk.Entry(que_win, width=30, textvariable=subject)
        subject_ent.place(x=155, y=0)

        mark_ent = ttk.Entry(que_win, width=10, textvariable=mark)
        mark_ent.place(x=140, y=30)

        que_txt = tk.Text(que_win, height=13, width=50)
        que_txt.place(x=0, y=80)

        send_btn = ttk.Button(que_win, text="Добавить вопрос", command=send)
        send_btn.place(x=0, y=310)

        que_win.mainloop()

    def seek_works():
        result_str = "Непроверенные работы:\n"
        for smth in examiner.is_unchecked_works():
            result_str += "{}\n".format(smth[0])

        if len(result_str) == 22:
            showinfo("Информация", "Непроверенные работы отсутствуют")
        else:
            showinfo("ID непроверенных работ", result_str)

    def check_work():
        def open_work():
            os.system("xdg-open works/{}.pdf".format(work_id.get()))

        def rate():
            if work_id.get() == "" or mark.get() == "":
                showerror("Error", "Введите данные")
            else:
                examiner.check_work(work_id.get(), mark.get())
                check_win.destroy()

        check_win = Tk()
        check_win.title("Проверка работы")
        check_win.minsize(height=400, width=500)
        check_win.maxsize(height=400, width=500)

        work_lbl = ttk.Label(check_win, text="ID работы :")
        work_lbl.place(x=0, y=0)

        mark_lbl = ttk.Label(check_win, text="Оценка :")
        mark_lbl.place(x=0, y=30)

        work_id = tk.IntVar()
        work_id_ent = ttk.Entry(check_win, width=30, textvariable=work_id)
        work_id_ent.place(x=100, y=0)

        mark = tk.IntVar()
        mark_ent = ttk.Entry(check_win, width=7, textvariable=mark)
        mark_ent.place(x=100, y=30)

        get_work_btn = ttk.Button(check_win, text="Открыть работу",
                                  command=open_work)
        get_work_btn.place(x=0, y=60)

        submit_mark_btn = ttk.Button(check_win, text="Оценить работу",
                                     command=rate)
        submit_mark_btn.place(x=0, y=90)

        check_win.mainloop()

    ex_win = Tk()
    ex_win.title("СДСЭ")
    ex_win.minsize(height=25, width=40)
    ex_win.minsize(height=25, width=50)

    add_que_btn = ttk.Button(ex_win, text="Добавить вопрос", command=que_add)
    add_que_btn.place(x=0, y=0)

    check_work_btn = ttk.Button(ex_win, text="Непроверенные работы",
                                command=seek_works)
    check_work_btn.place(x=0, y=30)

    concrete_work_btn = ttk.Button(ex_win, text="Проверить работу",
                                   command=check_work)
    concrete_work_btn.place(x=0, y=60)

    ex_win.mainloop()


def signup_ui():
    # signup database connect 
    def action():
        if name.get() == "" or user_name.get() == "" or password.get() == "" \
                or very_pass.get() == "":
            showerror("Error", "All Fields Are Required", parent=win_sign_up)
        elif password.get() != very_pass.get():
            showerror("Error", "Password & Confirm Password Should Be Same",
                      parent=win_sign_up)
        else:
            try:
                reg_student(name.get(), user_name.get(), password.get(),
                            ExamDatabase().sql)

            except Exception as es:
                showerror("Error", f"Error Dui to : {str(es)}",
                          parent=win_sign_up)

            else:
                showinfo("Успех", "Вы успешно зарегестрированы",
                         parent=win_sign_up)
                clear()
                switch()

    # close signup function			
    def switch():
        win_sign_up.destroy()

    # clear data function
    def clear():
        name.delete(0, tk.END)
        user_name.delete(0, tk.END)
        password.delete(0, tk.END)
        very_pass.delete(0, tk.END)

    # start Signup Window	

    win_sign_up = Tk()
    win_sign_up.title("СДСЭ")
    win_sign_up.maxsize(width=500, height=400)
    win_sign_up.minsize(width=500, height=400)

    # heading label
    heading = ttk.Label(win_sign_up, text="Регистрация студентов",
                        font='Verdana 20 bold')
    heading.place(x=80, y=60)

    # form data ttk.Label
    name = ttk.Label(win_sign_up, text="Полное имя :",
                     font='Verdana 10 bold')
    name.place(x=80, y=130)

    user_name = ttk.Label(win_sign_up, text="Логин :",
                          font='Verdana 10 bold')
    user_name.place(x=80, y=160)

    password = ttk.Label(win_sign_up, text="Пароль :", font='Verdana 10 bold')
    password.place(x=80, y=190)

    very_pass = ttk.Label(win_sign_up, text="Подтвердите:",
                          font='Verdana 10 bold')
    very_pass.place(x=80, y=220)

    # Entry Box ----------------------------------------------------------------

    name = tk.StringVar()
    user_name = tk.StringVar()
    password = tk.StringVar()
    very_pass = tk.StringVar()

    name = ttk.Entry(win_sign_up, width=30, textvariable=name)
    name.place(x=200, y=133)

    user_name = ttk.Entry(win_sign_up, width=30, textvariable=user_name)
    user_name.place(x=200, y=163)

    password = ttk.Entry(win_sign_up, width=30, textvariable=password)
    password.place(x=200, y=193)

    very_pass = ttk.Entry(win_sign_up, width=30, show="*",
                          textvariable=very_pass)
    very_pass.place(x=200, y=223)

    # button login and clear

    btn_signup = ttk.Button(win_sign_up, text="Регистрация", command=action)
    btn_signup.place(x=180, y=283)

    btn_login = ttk.Button(win_sign_up, text="Очистить", command=clear)
    btn_login.place(x=280, y=283)

    sign_up_btn = ttk.Button(win_sign_up, text="К авторизации",
                             command=switch)
    sign_up_btn.place(x=350, y=20)

    win_sign_up.mainloop()


def login_ui():
    def clear():
        user_entry.delete(0, tk.END)
        pass_entry.delete(0, tk.END)

    def login():
        if user_name.get() == "" or password.get() == "" or var.get() == "":
            showerror("Ошибка", "Введите все данные",
                      parent=win)
        else:
            log_id = -1
            try:
                log_id = enter_system(user_name.get(), password.get(),
                                      var.get(),
                                      ExamDatabase().sql)

            except ValueError:
                showerror("Ошибка", "Данный пользователь не существует")

            else:
                user_entry.delete(0, tk.END)
                pass_entry.delete(0, tk.END)
                win.destroy()
                if var.get() == 0:
                    student_ui(log_id[0])

                else:
                    examiner_ui(log_id[0])

    win = Tk()

    # app title
    win.title("СДСЭ")

    # window size
    win.maxsize(width=500, height=500)
    win.minsize(width=500, height=500)

    # heading label
    heading = ttk.Label(win, text="Авторизация", font='Verdana 25 bold')
    heading.place(x=80, y=150)

    username = ttk.Label(win, text="Логин :", font='Verdana 10 bold')
    username.place(x=80, y=220)

    userpass = ttk.Label(win, text="Пароль :", font='Verdana 10 bold')
    userpass.place(x=80, y=260)

    # Entry Box
    user_name = tk.StringVar()
    password = tk.StringVar()
    var = tk.IntVar()

    user_entry = ttk.Entry(win, width=40, textvariable=user_name)
    user_entry.focus()
    user_entry.place(x=200, y=223)

    pass_entry = ttk.Entry(win, width=40, show="*", textvariable=password)
    pass_entry.place(x=200, y=260)

    r_b_st = ttk.Radiobutton(win, text='Студент', value=0,
                             variable=var).place(x=160, y=285)
    r_b_ex = ttk.Radiobutton(win, text='Эказменатор',
                             value=1, variable=var).place(
        x=270, y=285)

    # button login and clear

    btn_login = ttk.Button(win, text="Войти", command=login)
    btn_login.place(x=180, y=320)

    btn_login = ttk.Button(win, text="Очистить", command=clear)
    btn_login.place(x=260, y=320)

    # signup button

    sign_up_btn = ttk.Button(win, text="Зарегистрироваться", command=signup_ui)
    sign_up_btn.place(x=340, y=20)

    win.mainloop()


if __name__ == '__main__':
    try:
        login_ui()
        #exam_reg_ui(Student(158151843))
    except Exception:
        showerror("Error", "Ошибка")
