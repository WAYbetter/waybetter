<!-- uncomment for jsp file -->
<!--
<%@ page language="java" contentType="text/html; charset=utf-8"
	pageEncoding="utf-8" errorPage="/error.jsp"%>

<jsp:useBean id="transactionDetails" scope="request" type="com.creditguard.common.transactions.TransactionDetails" />
<%@ include file="/merchantPages/WebSources/includes/main.jsp" %>
-->

    <%
	String langdir="ltr";
	String absvertpos="right: 0";
    if(lang.equals("HE")){
        langdir="rtl";
        absvertpos="left: 0";
    }
    %>

{% extends "wb_base_site.html" %}
{% load i18n %}
{% block bodyclass %}{{ block.super }} <%=langdir%>{% endblock %}
{% block extrahead %}
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="cache-control" content="no-cache">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="-1">
    <script src="merchantPages/WebSources/js/<%=lang%>.js"></script>
    <script src="merchantPages/WebSources/js/main.js"></script>

{% endblock %}
{% block extrastyle %}
    {{ block.super }}
    <style type="text/css">
        #creditForm{
            direction: <%=langdir%>;
        }
        #content-container {
            min-height: 0;
        }

        #site-content, #top-container {
            width: 450px;
        }

        .td_style_fieldName {
            font-weight: bold;
            font-size: 13px;
            width: 150px;
            height: 50px;
        }

        input {
            height: 25px;
        }

        #cardNumber, #personalId {
            width: 210px;
        }

        #cvv {
            width: 50px;
        }

        #qm {
            display: inline-block;
            height: 18px;
            width: 18px;
            position: relative;
            top: 3px;
            margin-right: 10px;
            cursor: pointer;
            background: url("/static/images/wb_site/question_mark.png") left 0 no-repeat;
        }

        #wb_CVVhelp {
            display: none;
            position: absolute;
            width: 225px;
            height: 125px;
            background: url("/static/images/wb_site/cvv.png") left 0 no-repeat;
        }

        #wb_lock {
            width: 33px;
            height: 52px;
            background: url("/static/images/wb_site/lock.png") left 0 no-repeat;
            display: inline-block;
            position: relative;
            top: 22px;
        }

        #wb_content_footer {
            border-top: 1px solid #BCBCBC;
            padding-top: 20px;
            margin-top: 40px;
            position: relative;
        }

        #footer_logos {
        }

        #wb_cg_logo {
            display: inline-block;
            width: 200px;
            height: 44px;
            background: url("/static/images/wb_site/credit-guard.png") left 0 no-repeat;
        }

        #wb_cards {
            display: inline-block;
            width: 218px;
            height: 40px;
            background: url("/static/images/wb_site/card_types.png") left 0 no-repeat;
        }

        #button_container {
            position: relative;
            height: 50px;
            margin-top: 35px;
        }

        #resetBtn{
            display:none;
        }
        #submitBtn {
            position: absolute;
            bottom: 0;
            <%=absvertpos%>;
        }

        #site-footer {
            position: relative;
            padding-top: 20px;
            direction: <%=langdir%>;
            width: 500px;
        }

        #wb_ssl {
            width: 117px;
            height: 58px;
            background: url("/static/images/wb_site/ssl.png") left 0 no-repeat;
            display: inline-block;
        }
        #wb_ssl_text {
            position: absolute;
            top: 20px;
            display: inline-block;
        <% if (langdir.equals("ltr")) { %>
            margin-left: 20px;
        <% } else { %>
            margin-right: 20px;
        <% } %>
            color: white;
        }


    </style>

{% endblock %}

{% block header_links %}{% endblock %}
{% block top_left %}
    <%=pageTitle%>
{% endblock %}

{% block top_right %}
    <% if (lang.equals("HE")) { %>
    תשלום מאובטח
    <% } else { %>
Secured Payment
    <% } %>
    <div id="wb_lock"></div>
{% endblock %}

{% block content %}
    <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard">
        <input type="hidden" name="txId" value="<%=mpiTxnId%>"/>
        <input type="hidden" name="lang" value="EN"/>
        <input type="hidden" name="track2" value="" autocomplete="off"/>
        <input type="hidden" name="last4d" value="" autocomplete="off"/>
        <input type="hidden" name="cavv" value="" autocomplete="off"/>
        <input type="hidden" name="eci" value="" autocomplete="off"/>
        <input type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>
        <table class="data_tbl">
            <tr>
                <td class="td_style_fieldName"><%=CCNumber%></td>
                <td><input type="text" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/></td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName"><%=CCExp%></td>
                <td>
                    <select id="expYear" name="expYear">
                        <%=expYear%>
                    </select>
                    -
                    <select id="expMonth" name="expMonth">
                        <option value="01">01</option>
                        <option value="02">02</option>
                        <option value="03">03</option>
                        <option value="04">04</option>
                        <option value="05">05</option>
                        <option value="06">06</option>
                        <option value="07">07</option>
                        <option value="08">08</option>
                        <option value="09">09</option>
                        <option value="10">10</option>
                        <option value="11">11</option>
                        <option value="12">12</option>
                    </select>
                </td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName">CVV</td>
                <td><input type="text" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                    <span id="qm" src="merchantPages/WebSources/images/qm.png"></span>

                    <span id="wb_CVVhelp"></span>
                </td>
                <td class="td_style_fieldName"></td>
            </tr>
            <tr>
                <td class="td_style_fieldName"><%=CCPId%></td>
                <td><input type="text" id="personalId" name="personalId" maxlength="9" autocomplete="off"/></td>
                <td class="td_style_fieldName"></td>
            </tr>
        </table>
        <div id="wb_content_footer">
            <div id="footer_logos">
                <div id="wb_cg_logo"></div>
                <div id="wb_cards"></div>
            </div>
            <div id="button_container">
                <input type="submit" class="wb_button" id="submitBtn" value="<%=formSend%>"/>
                <input id="resetBtn" type="reset" value="<%=formReset%>"/>
            </div>
        </div>
    </form>

{% endblock %}

{% block post_content %}
{% endblock %}

{% block footer %}
    <div id="wb_ssl"></div>
    <div id="wb_ssl_text">
        <% if (lang.equals("HE")) { %>
בדף זה אתה יכול לשלם על הזמנותיך מהאתר WAYbetter.com
        <br/>
הליך התשלום מאובטח ועומד בסטנדרטים הגבוהים ביותר של אבטחת מידע.
        <br/>
נא למלא את פרטי כרטיס האשראי בטופס לעיל.
        <br/>
התשלום עבור ההזמנה יגבה רק לאחר שליחת המונית.
        <% } else { %>
In this page you can pay for the order you placed on WAYbetter.com
        <br/>
The payment process is fully secure and complies with the highest standards of data protection.
        <br/>
Please insert your credit card details as required above.
        <br/>
Payment for the order will only be auctioned the taxi has been dispatched.
        <% } %>
    </div>
{% endblock %}

{% block scripts %}{% endblock %}
{% block doc_ready %}
    <script type="text/javascript">
        $(function() {
            $("#wb_logo").click(function() {
                window.location.href = "http://www.waybetter.com";
            });
            $("#lang_dropdown").hide();
            $("#qm").bind("mouseover mouseout", function() {
                var $help = $("#wb_CVVhelp");
                if ($help.is(":visible")) {
                    $help.hide();
                }
                else {
                    $help.show();
                }
            });


        })
    </script>
{% endblock %}